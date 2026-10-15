"""FastAPI application: wires storage, ML, engine, ingest source, tick loop and WebSocket fan-out."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routes import router
from .config import Settings, get_settings
from .core.auth import UserStore
from .core.logging import setup_logging
from .engine import Engine
from .ml.scorer import AnomalyScorer
from .services.ingest import DirectSource, MqttSource, backfill
from .storage.base import Repository, create_repository
from .ws.manager import WSManager

log = logging.getLogger("app")


@dataclass
class Ctx:
    settings: Settings
    repo: Repository
    scorer: AnomalyScorer
    engine: Engine
    ws: WSManager
    source: Any = None
    last_snapshot: dict | None = None
    last_snapshot_text: str | None = None
    tasks: list = field(default_factory=list)


async def tick_loop(c: Ctx) -> None:
    interval = c.settings.tick_ms / 1000.0
    nxt = time.monotonic()
    last_flush = 0.0
    while True:
        try:
            snap = c.engine.tick()
            snap["ws_clients"] = c.ws.count
            text = json.dumps(snap, separators=(",", ":"), allow_nan=False, default=str)
            c.last_snapshot, c.last_snapshot_text = snap, text
            c.ws.broadcast(text)
            if c.engine.events:
                events, c.engine.events = c.engine.events, []
                for ev in events:
                    c.ws.broadcast(json.dumps(ev, separators=(",", ":"), default=str), important=True)
            now = time.monotonic()
            if c.repo.mode == "db" and now - last_flush >= 1.0:
                last_flush = now
                c.engine.flush_telemetry()      # enqueue only; the repo writes from its own thread
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("tick failed - continuing")
        nxt += interval
        await asyncio.sleep(max(0.0, nxt - time.monotonic()))
        if nxt < time.monotonic() - 2:
            nxt = time.monotonic()


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    setup_logging(s.log_level, s.log_json)
    from simulator import Factory, build_profiles
    import os

    os.environ.setdefault("MACHINE_COUNT", str(s.machine_count))
    profiles = build_profiles(s.machine_count)

    repo = create_repository(s)
    await asyncio.to_thread(repo.start)
    scorer = AnomalyScorer(s.model_path)
    await asyncio.to_thread(scorer.load)
    engine = Engine(s, repo, scorer, profiles)
    repo.sync_machines(engine.machine_info())
    repo.save_model_info(scorer.meta)
    await asyncio.to_thread(engine.load_persisted)
    users = UserStore(s.users)
    app.state.users = users
    await asyncio.to_thread(repo.sync_users, users.export())
    ws = WSManager()
    c = Ctx(s, repo, scorer, engine, ws)
    app.state.ctx = c

    now = time.time()
    factory = Factory(profiles, seed=s.sim_seed, start_ts=now - max(s.backfill_days, 0) * 86400, random_events=True)
    if s.backfill_days > 0:
        await asyncio.to_thread(backfill, engine, factory, s.backfill_days, now)
    for m in factory.machines.values():
        m.random_events = False          # history had unplanned stops; live data stays calm unless you inject faults
        m.status, m.status_until = "RUNNING", 0.0     # start the live feed from a healthy, warmed-up machine
        m.temp, m.vib, m.temp_fault, m.vib_fault, m.noise_fault = m.p.base_temp, m.p.base_vib, 0.0, 0.0, 0.0
        m.clear()

    if s.ingest_mode == "mqtt":
        c.source = MqttSource(engine, s)
    else:
        c.source = DirectSource(engine, s, factory)
    await c.source.start()
    c.tasks.append(asyncio.create_task(tick_loop(c), name="tick"))
    if s.demo_hints:
        log.warning("DEMO_HINTS=true: demo logins are shown on the sign-in form. Set DEMO_HINTS=false and change USERS in .env "
                    "before exposing this service to anyone else.")
    log.info("ready: %d machines | ingest=%s | storage=%s | ml=%s", len(profiles), s.ingest_mode, repo.mode, scorer.ready)
    try:
        yield
    finally:
        for t in c.tasks:
            t.cancel()
        await c.source.stop()
        engine.flush_hourly()
        engine.flush_telemetry()
        await asyncio.to_thread(repo.stop)


app = FastAPI(
    title="AI-Enhanced Real-Time OEE & Anomaly Dashboard",
    description="Smart-factory monitor: telemetry ingest, OEE, rule/ML/What-If alerts, maintenance and reports. "
                "Write operations use HTTP Basic auth (see /config for the demo logins).",
    version="1.0.0", lifespan=lifespan,
)
_cors = get_settings().cors_origins
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in _cors.split(",")], allow_methods=["*"],
                   allow_headers=["*"], allow_credentials=False)
app.include_router(router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    resp.headers.setdefault("Cache-Control", "no-store")
    return resp


@app.exception_handler(Exception)
async def unhandled(_request: Request, exc: Exception):
    logging.getLogger("app").exception("unhandled error")
    return JSONResponse({"detail": "Something went wrong on the server. Please try again in a moment."}, status_code=500)
