"""Telemetry sources + simulator control.

* ``DirectSource`` - runs the virtual factory in-process (INGEST_MODE=direct, zero infrastructure).
* ``MqttSource``   - subscribes to Mosquitto (INGEST_MODE=mqtt, the production path) with automatic
  reconnect (1 s -> 5 s exponential back-off, NFR-R2).
Both expose the same control surface used by the REST API (inject / clear / speed).
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Any

import paho.mqtt.client as mqtt

from ..config import Settings
from ..engine import Engine

log = logging.getLogger("ingest")
TOPIC_TELEMETRY = "factory/telemetry"
TOPIC_CONTROL = "factory/control"
TOPIC_STATUS = "factory/sim/status"


# ====================================================================== history back-fill
def backfill(engine: Engine, factory, days: float, now: float) -> None:
    """Fast-forward the simulator through ``days`` of history (OEE windows, reports, chart buffers).

    This is simulated history (the dashboard says so); alerts and ML are not replayed.
    """
    from ..engine import STATUS_CODE

    t0 = time.time()
    start = now - days * 86400
    ts = start
    n = 0
    coarse_from = now - 8 * 3600
    while ts < now:
        dt = 10.0 if ts < now - 12 * 3600 else 5.0
        ts = min(ts + dt, now)
        for s in factory.step(dt, ts):
            ms = engine.machines[s["machine_id"]]
            ms.oee.update(ts, s["status"], s["cycle_count"], s["good_count"])
            if ts >= coarse_from and ts - ms._last_coarse >= 5.0:
                ms._last_coarse = ts
                ms.coarse.append([ts, s["temperature"], s["vibration"], STATUS_CODE[s["status"]], s["cycle_count"], None,
                                  s["machine_id"]])
            n += 1
    for ms in engine.machines.values():
        ms.oee.reset_baseline()          # live counters start from their own baseline
    engine.backfill_until_hour = int(now // 3600) * 3600
    engine.backfill_info = {"days": days, "seconds": round(time.time() - t0, 2), "samples": n,
                            "note": "simulated history for 1h/8h windows and 7-day reports"}
    log.info("back-filled %.1f days (%d samples) in %.1fs", days, n, time.time() - t0)


# ====================================================================== direct (in-process) source
class DirectSource:
    kind = "direct"

    def __init__(self, engine: Engine, settings: Settings, factory):
        self.engine, self.s, self.factory = engine, settings, factory
        self._task: asyncio.Task | None = None
        self.interval = 0.5

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="direct-sim")
        self.engine.mqtt_status = {"enabled": False, "connected": None, "note": "INGEST_MODE=direct"}

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()

    async def _run(self) -> None:
        nxt = time.monotonic()
        while True:
            ts = time.time()
            for sample in self.factory.step(self.interval, ts):
                self.engine.ingest(sample)
            self.engine.sim_status = {"mode": "direct", "machines": len(self.factory.machines),
                                      "interval_ms": int(self.interval * 1000), "time_scale": self.factory.time_scale,
                                      "faults": self.factory.active_faults(ts)}
            nxt += self.interval
            await asyncio.sleep(max(0.0, nxt - time.monotonic()))
            if nxt < time.monotonic() - 1:
                nxt = time.monotonic()

    # ---- control
    def inject(self, machine_id: str, kind: str, duration_s: float | None) -> dict[str, Any]:
        return self.factory.inject(machine_id, kind, time.time(), duration_s)

    def clear(self, machine_id: str | None) -> None:
        self.factory.clear(machine_id)

    def set_speed(self, factor: float) -> None:
        self.factory.time_scale = factor


# ====================================================================== MQTT source
class MqttSource:
    kind = "mqtt"

    def __init__(self, engine: Engine, settings: Settings):
        self.engine, self.s = engine, settings
        self.loop: asyncio.AbstractEventLoop | None = None
        self.client: mqtt.Client | None = None
        self.state: dict[str, Any] = {"enabled": True, "connected": False, "reconnects": 0, "last_connect": None,
                                      "last_disconnect": None, "last_message": None, "host": settings.mqtt_host,
                                      "port": settings.resolved_mqtt_port, "transport": settings.mqtt_transport}
        self._lock = threading.Lock()
        self._seen_connect = False

    async def start(self) -> None:
        self.loop = asyncio.get_running_loop()
        s = self.s
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="oee-backend", transport=s.mqtt_transport)
        if s.mqtt_transport == "websockets":
            c.ws_set_options(path=s.mqtt_ws_path)
        if s.mqtt_username:
            c.username_pw_set(s.mqtt_username, s.mqtt_password)
        c.reconnect_delay_set(min_delay=1, max_delay=5)       # exponential back-off, capped at 5 s
        c.on_connect, c.on_disconnect, c.on_message = self._on_connect, self._on_disconnect, self._on_message
        c.connect_async(s.mqtt_host, s.resolved_mqtt_port, keepalive=10)
        c.loop_start()
        self.client = c
        self.engine.mqtt_status = self.state
        log.info("MQTT source started -> %s:%s (%s)", s.mqtt_host, s.resolved_mqtt_port, s.mqtt_transport)

    async def stop(self) -> None:
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

    # ---- paho callbacks (run in paho's network thread)
    def _on_connect(self, client, _u, _flags, rc, _props=None):
        ok = not rc.is_failure if hasattr(rc, "is_failure") else rc == 0
        with self._lock:
            self.state.update(connected=ok, last_connect=time.time())
            if self._seen_connect:
                self.state["reconnects"] += 1
            self._seen_connect = True
        if ok:
            client.subscribe([(f"{TOPIC_TELEMETRY}/#", 0), (TOPIC_STATUS, 0)])
            log.info("MQTT connected")
        else:
            log.error("MQTT connect refused: %s", rc)

    def _on_disconnect(self, _c, _u, _flags, rc=None, _props=None):
        with self._lock:
            self.state.update(connected=False, last_disconnect=time.time())
        log.warning("MQTT disconnected (%s) - automatic reconnect with back-off (1s..5s)", rc)

    def _on_message(self, _c, _u, msg):
        try:
            payload = json.loads(msg.payload)
        except Exception:
            self.engine.stats["invalid"] += 1
            return
        self.state["last_message"] = time.time()
        if msg.topic == TOPIC_STATUS:
            self.loop.call_soon_threadsafe(self._set_sim_status, payload)
        elif isinstance(payload, dict):
            self.loop.call_soon_threadsafe(self.engine.ingest, payload)

    def _set_sim_status(self, payload: dict) -> None:
        self.engine.sim_status = {"mode": "mqtt", **payload}

    # ---- control (publish commands to the simulator process)
    def _publish(self, cmd: dict[str, Any]) -> None:
        if not self.client or not self.state["connected"]:
            raise RuntimeError("MQTT broker is not connected - cannot reach the simulator")
        self.client.publish(TOPIC_CONTROL, json.dumps(cmd), qos=1)

    def inject(self, machine_id: str, kind: str, duration_s: float | None) -> dict[str, Any]:
        self._publish({"cmd": "inject", "machine_id": machine_id, "kind": kind, "duration_s": duration_s})
        return {"machine_id": machine_id, "kind": kind, "start": time.time(), "duration": duration_s}

    def clear(self, machine_id: str | None) -> None:
        self._publish({"cmd": "clear", "machine_id": machine_id})

    def set_speed(self, factor: float) -> None:
        self._publish({"cmd": "scale", "factor": factor})
