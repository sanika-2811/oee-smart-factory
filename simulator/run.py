"""Live MQTT publisher:  ``python -m simulator.run``

Publishes ``factory/telemetry/<machine_id>`` every INTERVAL_MS (default 500 ms) and listens on
``factory/control`` for fault-injection commands. Reconnects automatically (1 s -> 5 s back-off)
so a broker restart never needs a manual restart of the simulator (NFR-R2).
"""
from __future__ import annotations

import json
import logging
import os
import signal
import time

import paho.mqtt.client as mqtt

from .core import FAULT_KINDS, Factory
from .profiles import build_profiles

log = logging.getLogger("simulator")

TOPIC_TELEMETRY = "factory/telemetry"
TOPIC_CONTROL = "factory/control"
TOPIC_STATUS = "factory/sim/status"


def make_client(client_id: str) -> mqtt.Client:
    transport = os.environ.get("MQTT_TRANSPORT", "websockets")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id, transport=transport)
    if transport == "websockets":
        client.ws_set_options(path=os.environ.get("MQTT_WS_PATH", "/"))
    user = os.environ.get("MQTT_USERNAME")
    if user:
        client.username_pw_set(user, os.environ.get("MQTT_PASSWORD", ""))
    client.reconnect_delay_set(min_delay=1, max_delay=5)
    return client


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    interval = int(os.environ.get("INTERVAL_MS", "500")) / 1000.0
    host = os.environ.get("MQTT_HOST", "localhost")
    default_port = "9001" if os.environ.get("MQTT_TRANSPORT", "websockets") == "websockets" else "1883"
    port = int(os.environ.get("MQTT_PORT", default_port))
    factory = Factory(build_profiles(), seed=int(os.environ["SIM_SEED"]) if os.environ.get("SIM_SEED") else None)

    client = make_client("virtual-factory-sim")

    def on_connect(c, _u, _f, rc, _p=None):
        log.info("connected to broker %s:%s (rc=%s)", host, port, rc)
        c.subscribe(TOPIC_CONTROL, qos=1)

    def on_disconnect(_c, _u, _f, rc, _p=None):
        log.warning("disconnected from broker (rc=%s) - retrying automatically", rc)

    def on_message(_c, _u, msg):
        try:
            cmd = json.loads(msg.payload)
            action = cmd.get("cmd")
            now = time.time()
            if action == "inject" and cmd.get("kind") in FAULT_KINDS:
                info = factory.inject(cmd["machine_id"], cmd["kind"], now, cmd.get("duration_s"))
                log.info("fault injected: %s", info)
            elif action == "clear":
                factory.clear(cmd.get("machine_id"))
                log.info("faults cleared: %s", cmd.get("machine_id") or "all")
            elif action == "scale":
                factory.time_scale = max(0.5, min(float(cmd.get("factor", 1)), 10.0))
                log.info("fault time-compression set to x%.1f", factory.time_scale)
        except Exception:  # never let a bad control message stop the simulator
            log.exception("bad control message: %r", msg.payload[:200])

    client.on_connect, client.on_disconnect, client.on_message = on_connect, on_disconnect, on_message
    client.connect_async(host, port, keepalive=10)
    client.loop_start()

    stop = False

    def _stop(*_):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    n = len(factory.machines)
    log.info("simulating %d machines every %.0f ms -> %s:%s (%s)", n, interval * 1000, host, port,
             os.environ.get("MQTT_TRANSPORT", "websockets"))
    next_tick = time.monotonic()
    last_status = 0.0
    while not stop:
        ts = time.time()
        for sample in factory.step(interval, ts):
            if client.is_connected():
                client.publish(f"{TOPIC_TELEMETRY}/{sample['machine_id']}", json.dumps(sample), qos=0)
        if ts - last_status > 5 and client.is_connected():
            last_status = ts
            client.publish(TOPIC_STATUS, json.dumps({
                "machines": n, "interval_ms": int(interval * 1000), "time_scale": factory.time_scale,
                "faults": factory.active_faults(ts), "ts": ts}), qos=0, retain=True)
        next_tick += interval
        delay = next_tick - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        else:
            next_tick = time.monotonic()
    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()
