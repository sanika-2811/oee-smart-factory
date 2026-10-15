"""End-to-end smoke test (definition of done).

Starts the backend in INGEST_MODE=direct, waits for data and asserts:
  * 5 machines streaming, OEE within 0-100 %
  * an Orange alert during a temperature ramp, then a Red alert, plus a Yellow ML caution
  * dashboard update latency < 1 s and ML inference < 200 ms
  * 50 concurrent WebSocket clients all receive snapshots

    python scripts/smoke_test.py
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("SMOKE_PORT", "8765"))
BASE = f"http://127.0.0.1:{PORT}"
AUTH = "Basic " + base64.b64encode(b"manager:manager123").decode()
results: list[tuple[str, bool, str]] = []
t_start = 0.0


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(("  PASS " if ok else "  FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)


def call(path: str, method: str = "GET", body: dict | None = None, auth: bool = False):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    if auth:
        req.add_header("Authorization", AUTH)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def alive() -> bool:
    try:
        urllib.request.urlopen(BASE + "/health", timeout=2).read()
        return True
    except Exception:
        return False


def wait_for(fn, timeout: float, every: float = 0.5):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            v = fn()
        except Exception:
            v = None
        if v:
            return v
        time.sleep(every)
    return None


def alerts_of(level: str, machine: str):
    _, rows = call(f"/alerts?level={level}&machine_id={machine}&limit=20")
    return [a for a in rows if a["opened_at"] > t_start]


def streaming() -> bool:
    _, ms = call("/machines")
    return len(ms) == 5 and all(m["live"] and m["live"]["temperature"] is not None for m in ms)


async def ws_clients(n: int, seconds: float = 3.0) -> int:
    import websockets

    async def one():
        async with websockets.connect(f"ws://127.0.0.1:{PORT}/ws/live", max_size=2**22) as ws:
            got = 0
            end = time.time() + seconds
            while time.time() < end:
                msg = json.loads(await asyncio.wait_for(ws.recv(), 3))
                got += msg.get("type") == "snapshot"
            return got

    res = await asyncio.gather(*[one() for _ in range(n)], return_exceptions=True)
    return sum(1 for r in res if isinstance(r, int) and r >= 3)


def main() -> int:
    global t_start
    env = {**os.environ, "INGEST_MODE": "direct", "STORAGE_MODE": "memory", "BACKFILL_DAYS": "0.25",
           "LOG_LEVEL": "WARNING", "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT), "--log-level", "warning"],
                            cwd=ROOT / "backend", env=env)
    try:
        print("starting backend ...", flush=True)
        check("backend starts", bool(wait_for(alive, 90, 1)))
        t_start = time.time()
        wait_for(streaming, 20)
        _, ms = call("/machines")
        live = [m["live"] for m in ms if m["live"]]
        check("5 machines streaming", len(live) == 5 and all(m["online"] for m in live), f"{len(live)} live")
        _, o = call("/oee?window=1h")
        vals = [o["plant"][k] for k in ("oee", "availability", "performance", "quality")]
        check("OEE within 0-100 % (1 h)", all(0 <= v <= 100 for v in vals) and o["plant"]["oee"] > 0,
              f"OEE={o['plant']['oee']}% A={o['plant']['availability']} P={o['plant']['performance']} Q={o['plant']['quality']}")
        _, o8 = call("/oee?window=8h")
        check("8 h window available", 0 < o8["plant"]["oee"] <= 100, f"OEE8h={o8['plant']['oee']}%")

        ok_clients = asyncio.run(ws_clients(50))
        check("50 concurrent WebSocket clients", ok_clients == 50, f"{ok_clients}/50 received >=3 snapshots")

        code, _ = call("/simulator/inject-fault", "POST", {"machine_id": "CNC-01", "kind": "temp_ramp"})
        check("fault injection requires auth", code == 401, f"HTTP {code}")
        code, _ = call("/simulator/inject-fault", "POST", {"machine_id": "CNC-01", "kind": "temp_ramp", "duration_s": 75}, auth=True)
        check("temperature ramp injected", code == 200, f"HTTP {code}")
        orange = wait_for(lambda: alerts_of("orange", "CNC-01"), 80)
        check("Orange (What-If) alert during the ramp", bool(orange), f"eta={orange[0]['eta_s']}s" if orange else "none")
        red = wait_for(lambda: alerts_of("red", "CNC-01"), 60)
        check("Red alert once temperature > limit", bool(red), red[0]["message"] if red else "none")
        call("/simulator/clear", "POST", {"machine_id": "CNC-01"}, auth=True)

        call("/simulator/inject-fault", "POST", {"machine_id": "Welder-04", "kind": "anomaly", "duration_s": 60}, auth=True)
        yellow = wait_for(lambda: alerts_of("yellow", "Welder-04"), 40)
        check("Yellow ML caution (score > 85 %)", bool(yellow), f"score={yellow[0].get('score')}" if yellow else "none")
        call("/simulator/clear", "POST", {"machine_id": None}, auth=True)

        _, m = call("/metrics")
        lat, inf = m["latency_ms"], m["inference_ms"]
        check("update latency < 1 s (p95)", lat["p95"] is not None and lat["p95"] < 1000, f"p95={lat['p95']} ms max={lat['max']} ms")
        check("ML inference < 200 ms (max)", inf["max"] is not None and inf["max"] < 200, f"max={inf['max']} ms p95={inf['p95']} ms")
        _, h = call("/health")
        check("/health reports storage mode", h.get("storage_mode") == "memory", f"{h.get('storage_mode')} influx={h.get('influx')} postgres={h.get('postgres')}")
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except Exception:
            proc.kill()
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
