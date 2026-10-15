"""MQTT path + reconnect test (NFR-R2: reconnect within 5 s).

Starts a dev broker (pure-Python amqtt, TCP), the simulator and the backend in INGEST_MODE=mqtt, then:
  1. checks telemetry flows over MQTT and a fault injected through the MQTT control channel raises an alert
  2. kills the broker, restarts it, and measures how long the backend and the simulator need to resume

Uses TCP because amqtt's WebSocket listener drops idle connections every ~20 s (a dev-broker quirk;
Mosquitto does not). The code path is identical - only the paho transport differs.

    python scripts/mqtt_resilience_test.py
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
API = "http://127.0.0.1:8011"
AUTH = "Basic " + base64.b64encode(b"manager:manager123").decode()
procs: list[subprocess.Popen] = []
ok_all = True


def check(name: str, ok: bool, detail: str = "") -> None:
    global ok_all
    ok_all &= ok
    print(("  PASS " if ok else "  FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)


def get(path: str, auth: bool = False, body: dict | None = None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None,
                                 method="POST" if body is not None else "GET")
    req.add_header("Content-Type", "application/json")
    if auth:
        req.add_header("Authorization", AUTH)
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read() or b"null")


def spawn(args, cwd=ROOT, **env):
    p = subprocess.Popen([PY, *args], cwd=cwd, env={**os.environ, **env}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    procs.append(p)
    return p


def wait_for(fn, timeout, every=0.1):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            v = fn()
            if v:
                return time.time() - t0
        except Exception:
            pass
        time.sleep(every)
    return None


def main() -> int:
    mqtt_env = dict(MQTT_HOST="127.0.0.1", MQTT_TRANSPORT="tcp", MQTT_PORT="1883")
    broker = spawn(["scripts/dev_broker.py"])
    time.sleep(3)
    spawn(["-m", "simulator.run"], PYTHONPATH=str(ROOT), **mqtt_env)
    spawn(["-m", "uvicorn", "app.main:app", "--port", "8011", "--log-level", "warning"], cwd=ROOT / "backend",
          INGEST_MODE="mqtt", BACKFILL_DAYS="0.05", LOG_LEVEL="WARNING", **mqtt_env)
    try:
        t = wait_for(lambda: get("/health")["mqtt"] is True, 60)
        check("backend connected to broker", t is not None)
        t = wait_for(lambda: get("/metrics")["ingest"]["rx"] > 20, 20)
        check("telemetry flows over MQTT", t is not None)
        get("/simulator/inject-fault", True, {"machine_id": "Press-02", "kind": "vib_spike", "duration_s": 15})
        t = wait_for(lambda: any(a["level"] == "red" for a in get("/alerts?machine_id=Press-02")), 20, 0.25)
        check("fault injected via MQTT control channel -> Red alert", t is not None, f"{t:.1f}s" if t else "")

        # ---- kill the broker
        broker.kill()
        time.sleep(1.5)
        check("backend notices broker loss", get("/health")["mqtt"] is False)
        rx_before = get("/metrics")["ingest"]["rx"]
        broker = spawn(["scripts/dev_broker.py"])
        t0 = time.time()
        t_conn = wait_for(lambda: get("/health")["mqtt"] is True, 30, 0.05)
        # the broker needs ~2 s to bind; measure from the moment its port accepts connections
        import socket

        def port_open():
            with socket.socket() as s:
                s.settimeout(0.2)
                return s.connect_ex(("127.0.0.1", 1883)) == 0

        t_port = wait_for(port_open, 15, 0.05)
        t_flow = wait_for(lambda: get("/metrics")["ingest"]["rx"] > rx_before + 10, 30, 0.1)
        reconnect_s = (time.time() - t0) - (t_port or 0) if t_flow is not None else None
        check("backend reconnects and data resumes within 5 s of the broker returning",
              t_flow is not None and reconnect_s is not None and reconnect_s <= 5.0,
              f"{reconnect_s:.1f}s after the broker accepted connections" if reconnect_s is not None else "never")
        check("reconnect counter incremented", get("/metrics")["mqtt"]["reconnects"] >= 1)
    finally:
        for p in procs:
            p.kill()
    print("PASSED" if ok_all else "FAILED")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
