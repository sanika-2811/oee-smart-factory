"""REST + WebSocket API (documented automatically at /docs, FR-12)."""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, WebSocket

from ..core.auth import CONTROL, OPERATE, User, require_roles, require_user
from ..schemas import (AssignIn, ClearFaultIn, FeedbackIn, InjectFaultIn, MaintenanceIn, MaintenancePatch, OutageIn,
                       ResolveIn, SpeedIn, TelemetryIn)

router = APIRouter()


def ctx(request: Request):
    return request.app.state.ctx


def _ts(value: str | float | None, default: float) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        raise HTTPException(422, f"Could not read the time value '{value}'. Use epoch seconds or an ISO date like 2026-10-15T10:30:00Z.")


def _machine(c, machine_id: str):
    if machine_id not in c.engine.machines:
        raise HTTPException(404, f"There is no machine called '{machine_id}'. Try one of: {', '.join(c.engine.machines)}.")
    return c.engine.machines[machine_id]


# ============================================================ system
@router.get("/health", tags=["system"], summary="Liveness + storage connectivity")
async def health(request: Request):
    c = ctx(request)
    h = c.repo.health()
    return {"status": "ok", "uptime_s": round(time.time() - c.engine.started, 1), "ingest_mode": c.settings.ingest_mode,
            "machines": len(c.engine.machines), "ml_ready": c.scorer.ready, **h,
            "mqtt": c.engine.mqtt_status.get("connected") if c.settings.ingest_mode == "mqtt" else "not used (direct mode)"}


@router.get("/config", tags=["system"], summary="Public client configuration")
async def config(request: Request):
    c = ctx(request)
    s = c.settings
    return {"ingest_mode": s.ingest_mode, "storage_mode": c.repo.mode, "machines": c.engine.machine_info(),
            "anomaly_threshold": s.anomaly_threshold, "whatif_horizon_s": s.whatif_horizon_s,
            "whatif_window_s": s.whatif_window_s, "tick_ms": s.tick_ms,
            "technicians": [t.strip() for t in s.technicians.split(",") if t.strip()],
            "demo_logins": [{"username": u.split(":")[0], "password": u.split(":")[1],
                             "role": u.split(":")[2] if len(u.split(":")) > 2 else ""}
                            for u in s.users.split(",") if u.count(":") >= 1] if s.demo_hints else [],
            "backfill": c.engine.backfill_info}


@router.get("/metrics", tags=["system"], summary="Performance + non-functional targets (live)")
async def metrics(request: Request):
    c = ctx(request)
    m = c.engine.metrics()
    m["ws"] = {"clients": c.ws.count, "peak": c.ws.peak, "total_connections": c.ws.total_connections}
    return m


@router.post("/auth/login", tags=["auth"], summary="Validate credentials (HTTP Basic)")
async def login(user: User = Depends(require_user)):
    return {"username": user.username, "role": user.role}


# ============================================================ machines / telemetry
@router.get("/machines", tags=["machines"], summary="All machines with their latest state")
async def machines(request: Request):
    c = ctx(request)
    snap = c.last_snapshot or {"machines": []}
    live = {m["id"]: m for m in snap["machines"]}
    return [{**info, "live": live.get(info["id"])} for info in c.engine.machine_info()]


@router.get("/machines/{machine_id}", tags=["machines"])
async def machine(machine_id: str, request: Request):
    c = ctx(request)
    _machine(c, machine_id)
    info = next(i for i in c.engine.machine_info() if i["id"] == machine_id)
    live = next((m for m in (c.last_snapshot or {"machines": []})["machines"] if m["id"] == machine_id), None)
    return {**info, "live": live}


@router.get("/machines/{machine_id}/telemetry", tags=["machines"], summary="Telemetry history")
async def telemetry(machine_id: str, request: Request,
                    from_: str | None = Query(None, alias="from", description="epoch seconds or ISO-8601 (default: 5 min ago)"),
                    to: str | None = Query(None, description="epoch seconds or ISO-8601 (default: now)"),
                    max_points: int = Query(1200, ge=10, le=5000)):
    c = ctx(request)
    _machine(c, machine_id)
    now = time.time()
    t_to = _ts(to, now)
    t_from = _ts(from_, t_to - 300)
    if t_from >= t_to:
        raise HTTPException(422, "'from' must be earlier than 'to'.")
    res = c.engine.telemetry(machine_id, t_from, t_to, max_points)
    if t_from < res["memory_covers_from"] and c.repo.mode == "db":
        hist = await asyncio.to_thread(c.repo.query_telemetry, machine_id, t_from, min(t_to, res["memory_covers_from"]), max_points)
        if hist:
            res["points"] = hist + res["points"]
            res["resolution"] = "mixed (influx + live)"
    res.pop("memory_covers_from", None)
    return res


@router.put("/machines/{machine_id}/thresholds", tags=["machines"], summary="Change hard limits (auth)")
async def thresholds(machine_id: str, request: Request, temp_limit: float | None = Query(None, gt=0, le=500),
                     vib_limit: float | None = Query(None, gt=0, le=100), user: User = Depends(require_roles(*CONTROL))):
    c = ctx(request)
    _machine(c, machine_id)
    return c.engine.set_thresholds(machine_id, temp_limit, vib_limit)


@router.get("/oee", tags=["oee"], summary="OEE = Availability x Performance x Quality")
async def oee(request: Request, window: str = Query("1h", pattern="^(1h|8h)$")):
    c = ctx(request)
    snap = c.last_snapshot
    if not snap:
        raise HTTPException(503, "The first data snapshot is not ready yet. Try again in a second.")
    return {"window": window, "plant": snap["plant"]["oee"][window],
            "machines": {m["id"]: m["oee"][window] for m in snap["machines"]},
            "formula": "OEE = Availability x Performance x Quality"}


@router.post("/telemetry", tags=["ingest"], summary="HTTP ingest gateway (validated, FR-09)", status_code=202)
async def post_telemetry(sample: TelemetryIn, request: Request, x_ingest_key: str | None = Header(None)):
    c = ctx(request)
    if c.settings.ingest_api_key and x_ingest_key != c.settings.ingest_api_key:
        raise HTTPException(401, "A valid X-Ingest-Key header is required to post telemetry.")
    ok, err = c.engine.ingest(sample.model_dump())
    if not ok:
        raise HTTPException(422, err)
    return {"accepted": True}


# ============================================================ alerts
@router.get("/alerts", tags=["alerts"], summary="Alert feed (live + history)")
async def alerts(request: Request, level: str | None = Query(None, pattern="^(yellow|orange|red)$"),
                 status: str | None = Query(None, pattern="^(open|acknowledged|cleared|resolved)$"),
                 machine_id: str | None = None, active: bool | None = None, limit: int = Query(200, ge=1, le=2000)):
    c = ctx(request)
    return [a.to_dict() for a in c.engine.alerts.list(level=level, status=status, machine_id=machine_id, active=active, limit=limit)]


def _alert_or_404(c, alert_id: int):
    a = c.engine.alerts.get(alert_id)
    if a is None:
        raise HTTPException(404, f"Alert #{alert_id} was not found. It may be older than the retained history.")
    return a


@router.get("/alerts/{alert_id}", tags=["alerts"])
async def alert(alert_id: int, request: Request):
    return _alert_or_404(ctx(request), alert_id).to_dict()


@router.post("/alerts/{alert_id}/ack", tags=["alerts"], summary="Acknowledge an alarm (auth)")
async def ack(alert_id: int, request: Request, user: User = Depends(require_roles(*OPERATE))):
    c = ctx(request)
    _alert_or_404(c, alert_id)
    return c.engine.alerts.acknowledge(alert_id, user.username).to_dict()


@router.post("/alerts/{alert_id}/assign", tags=["alerts"], summary="Assign a (virtual) technician (auth)")
async def assign(alert_id: int, body: AssignIn, request: Request, user: User = Depends(require_roles(*OPERATE))):
    c = ctx(request)
    _alert_or_404(c, alert_id)
    return c.engine.alerts.assign(alert_id, body.technician, user.username).to_dict()


@router.post("/alerts/{alert_id}/resolve", tags=["alerts"], summary="Close an issue with resolution notes (auth)")
async def resolve(alert_id: int, body: ResolveIn, request: Request, user: User = Depends(require_roles(*OPERATE))):
    c = ctx(request)
    _alert_or_404(c, alert_id)
    return c.engine.alerts.resolve(alert_id, user.username, body.notes).to_dict()


@router.post("/alerts/{alert_id}/feedback", tags=["alerts"], summary="ML accuracy feedback: true / false positive (auth)")
async def feedback(alert_id: int, body: FeedbackIn, request: Request, user: User = Depends(require_roles(*OPERATE))):
    c = ctx(request)
    _alert_or_404(c, alert_id)
    return c.engine.alerts.feedback(alert_id, user.username, body.verdict, body.comment).to_dict()


# ============================================================ maintenance
@router.get("/technicians", tags=["maintenance"])
async def technicians(request: Request):
    return [t.strip() for t in ctx(request).settings.technicians.split(",") if t.strip()]


@router.get("/maintenance", tags=["maintenance"], summary="Maintenance log")
async def maintenance_list(request: Request, machine_id: str | None = None, alert_id: int | None = None):
    c = ctx(request)
    rows = sorted(c.engine.maintenance.values(), key=lambda r: r["id"], reverse=True)
    return [r for r in rows if (not machine_id or r["machine_id"] == machine_id) and (alert_id is None or r.get("alert_id") == alert_id)]


@router.post("/maintenance", tags=["maintenance"], status_code=201, summary="Log a maintenance action (auth)")
async def maintenance_create(body: MaintenanceIn, request: Request, user: User = Depends(require_roles(*OPERATE))):
    c = ctx(request)
    _machine(c, body.machine_id)
    if body.alert_id is not None:
        a = _alert_or_404(c, body.alert_id)
        if a.machine_id != body.machine_id:
            raise HTTPException(422, "That alert belongs to a different machine.")
    return c.engine.add_maintenance(body.model_dump(), user.username)


@router.patch("/maintenance/{rec_id}", tags=["maintenance"], summary="Update / close a record (auth)")
async def maintenance_patch(rec_id: int, body: MaintenancePatch, request: Request, user: User = Depends(require_roles(*OPERATE))):
    c = ctx(request)
    if rec_id not in c.engine.maintenance:
        raise HTTPException(404, f"Maintenance record #{rec_id} was not found.")
    return c.engine.patch_maintenance(rec_id, body.model_dump(exclude_unset=True))


@router.delete("/maintenance/{rec_id}", tags=["maintenance"], status_code=204, summary="Delete a record (auth)")
async def maintenance_delete(rec_id: int, request: Request, user: User = Depends(require_roles(*OPERATE))):
    c = ctx(request)
    if rec_id not in c.engine.maintenance:
        raise HTTPException(404, f"Maintenance record #{rec_id} was not found.")
    c.engine.delete_maintenance(rec_id)


# ============================================================ simulator / what-if / ML control
def _control(c, fn, *args):
    try:
        return fn(*args)
    except KeyError as exc:
        raise HTTPException(404, f"Unknown machine {exc}.")
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))


@router.get("/simulator/status", tags=["simulator"])
async def sim_status(request: Request):
    return ctx(request).engine.sim_status


@router.post("/simulator/inject-fault", tags=["simulator"], summary="Inject a demo fault (auth)")
async def inject(body: InjectFaultIn, request: Request, user: User = Depends(require_roles(*CONTROL))):
    c = ctx(request)
    _machine(c, body.machine_id)
    info = _control(c, c.source.inject, body.machine_id, body.kind, body.duration_s)
    return {"injected": info, "by": user.username}


@router.post("/simulator/clear", tags=["simulator"], summary="Clear injected faults (auth)")
async def sim_clear(body: ClearFaultIn, request: Request, user: User = Depends(require_roles(*CONTROL))):
    c = ctx(request)
    _control(c, c.source.clear, body.machine_id)
    return {"cleared": body.machine_id or "all"}


@router.post("/simulator/speed", tags=["simulator"], summary="Fault time-compression for demos (auth)")
async def sim_speed(body: SpeedIn, request: Request, user: User = Depends(require_roles(*CONTROL))):
    c = ctx(request)
    _control(c, c.source.set_speed, body.factor)
    return {"time_scale": body.factor}


@router.get("/whatif/{machine_id}", tags=["what-if"], summary="Regression line y = m*x + c and projected threshold crossing")
async def whatif(machine_id: str, request: Request):
    c = ctx(request)
    _machine(c, machine_id)
    return c.engine.whatif_detail(machine_id)


@router.post("/whatif/{machine_id}/run", tags=["what-if"], summary="Start the 3-minute degradation scenario (auth)")
async def whatif_run(machine_id: str, request: Request, user: User = Depends(require_roles(*CONTROL))):
    c = ctx(request)
    _machine(c, machine_id)
    info = _control(c, c.source.inject, machine_id, "temp_ramp", None)
    return {"started": info, "by": user.username}


@router.post("/ml/outage", tags=["ml"], summary="Simulate an ML service outage (auth) - demonstrates NFR-R1")
async def ml_outage(body: OutageIn, request: Request, user: User = Depends(require_roles(*CONTROL))):
    c = ctx(request)
    c.scorer.outage = body.enabled
    return {"ml_outage": body.enabled}


# ============================================================ reports (FR-08)
async def _repo_rows(c, days: int):
    if c.repo.mode != "db":
        return None
    return await asyncio.to_thread(c.repo.query_hourly, time.time() - (days + 1) * 86400)


@router.get("/reports/oee-trend", tags=["reports"], summary="Daily OEE trend (default 7 days)")
async def report_oee(request: Request, days: int = Query(7, ge=1, le=365)):
    c = ctx(request)
    return c.engine.report_oee_trend(days, await _repo_rows(c, days))


@router.get("/reports/downtime", tags=["reports"], summary="Downtime per shift")
async def report_downtime(request: Request, days: int = Query(7, ge=1, le=365)):
    c = ctx(request)
    return c.engine.report_downtime(days, await _repo_rows(c, days))


@router.get("/reports/ml-accuracy", tags=["reports"], summary="ML accuracy from operator feedback")
async def report_ml(request: Request):
    return ctx(request).engine.report_ml_accuracy()


# ============================================================ live WebSocket
@router.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    c = ws.app.state.ctx
    if c.ws.count >= c.settings.max_ws_clients:
        await ws.close(code=1013)          # try again later: connection cap protects the 500 ms loop
        return
    hello = json.dumps({"type": "hello", "tick_ms": c.settings.tick_ms, "server_ts": time.time()})
    # greet + send the latest snapshot immediately (no waiting for the next tick)
    await c.ws.handle(ws, hello, *([c.last_snapshot_text] if c.last_snapshot_text else []))
