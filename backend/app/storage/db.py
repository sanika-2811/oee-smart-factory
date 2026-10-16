"""STORAGE_MODE=db : InfluxDB v2 (time series) + PostgreSQL (metadata) behind the Repository interface.

Design rules:
* Callers never block: every write is queued and executed by one background thread.
* Callers never crash: failures are logged, the affected sink is marked unhealthy and retried with
  back-off; the dashboard keeps serving from memory meanwhile.
* Telemetry is batched (flushed about once per second) so the 500 ms loop is unaffected.
"""
from __future__ import annotations

import json
import logging
import queue
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine as SAEngine

from .base import Repository

log = logging.getLogger("storage")
PG_BACKOFF = (2, 5, 10, 30)


def _dt(ts: float | None):
    return None if ts is None else datetime.fromtimestamp(ts, tz=timezone.utc)


class DbRepository(Repository):
    mode = "db"

    def __init__(self, settings):
        super().__init__()
        self.s = settings
        self.q: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=100_000)
        self.state = {"influx": "unknown", "postgres": "unknown"}
        self.last_error: dict[str, str] = {}
        self._pg: SAEngine | None = None
        self._influx = None
        self._write_api = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._pg_fail = 0
        self._pg_next = 0.0
        self._influx_next = 0.0
        self.dropped_points = 0

    # ================================================================== lifecycle
    def start(self) -> None:
        s = self.s
        self._pg = create_engine(s.postgres_url, pool_pre_ping=True, pool_size=3, max_overflow=2,
                                 connect_args={"connect_timeout": s.postgres_connect_timeout_s})
        try:
            from influxdb_client import InfluxDBClient
            from influxdb_client.client.write_api import SYNCHRONOUS

            self._influx = InfluxDBClient(url=s.influx_url, token=s.influx_token, org=s.influx_org, timeout=5000)
            self._write_api = self._influx.write_api(write_options=SYNCHRONOUS)
        except Exception as exc:
            self._set("influx", False, f"client setup failed: {exc}")
        self._probe()
        self._self_check_message()
        self._thread = threading.Thread(target=self._run, name="db-writer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=8)
        if self._influx:
            self._influx.close()
        if self._pg:
            self._pg.dispose()

    def _self_check_message(self) -> None:
        s = self.s
        problems = []
        if self.state["postgres"] != "ok":
            problems.append(f"  - PostgreSQL is not reachable at {s.postgres_host}:{s.postgres_port} (db '{s.postgres_db}', user "
                            f"'{s.postgres_user}'). Is the container running (`docker ps`) and is POSTGRES_PASSWORD correct? "
                            f"Last error: {self.last_error.get('postgres', '?')}")
        if self.state["influx"] != "ok":
            problems.append(f"  - InfluxDB is not reachable/authorised at {s.influx_url} (org '{s.influx_org}'). Check INFLUX_URL, "
                            f"INFLUX_TOKEN and INFLUX_ORG. Last error: {self.last_error.get('influx', '?')}")
        if problems:
            log.warning("STORAGE_MODE=db but some databases are not ready:\n%s\n  The dashboard keeps working from memory and "
                        "will retry every few seconds. Run `python -m app.storage.verify` for a step-by-step check.",
                        "\n".join(problems))
        else:
            log.info("storage: PostgreSQL ok, InfluxDB ok")

    def health(self) -> dict[str, Any]:
        out = {"storage_mode": "db", "influx": self.state["influx"], "postgres": self.state["postgres"],
               "queue": self.q.qsize(), "dropped_points": self.dropped_points}
        if self.last_error and (self.state["influx"] != "ok" or self.state["postgres"] != "ok"):
            out["last_error"] = {k: v for k, v in self.last_error.items() if self.state.get(k) != "ok"}
        return out

    def _set(self, which: str, ok: bool, err: str | None = None) -> None:
        new = "ok" if ok else "unreachable"
        if self.state[which] != new:
            (log.info if ok else log.warning)("storage: %s is now %s%s", which, new, "" if ok else f" ({err})")
        self.state[which] = new
        if err and not ok:
            self.last_error[which] = err[:300]

    def _probe(self) -> None:
        try:
            with self._pg.connect() as c:
                c.execute(text("SELECT 1"))
            self._set("postgres", True)
        except Exception as exc:
            self._set("postgres", False, str(exc).splitlines()[0])
        try:
            ok = bool(self._influx and self._influx.ping())
            self._set("influx", ok, None if ok else "ping failed")
        except Exception as exc:
            self._set("influx", False, str(exc).splitlines()[0])

    # ================================================================== public API (non-blocking writes)
    def _enqueue(self, kind: str, payload: Any) -> None:
        try:
            self.q.put_nowait((kind, payload))
        except queue.Full:
            if kind == "points":
                self.dropped_points += len(payload)
            else:
                log.error("storage queue full - dropping %s", kind)

    def write_telemetry(self, points: list[dict[str, Any]]) -> None:
        if points:
            self._enqueue("points", points)

    def upsert_hourly(self, rows: list[dict[str, Any]], only_missing: bool = False) -> None:
        super().upsert_hourly(rows, only_missing)     # keep a local copy as fallback
        self._enqueue("hourly_missing" if only_missing else "hourly", rows)

    def save_alert(self, alert: dict[str, Any]) -> None:
        self._enqueue("alert", alert)

    def save_maintenance(self, rec: dict[str, Any]) -> None:
        self._enqueue("maint", rec)

    def delete_maintenance(self, rec_id: int) -> None:
        self._enqueue("maint_del", rec_id)

    def save_machine(self, machine: dict[str, Any]) -> None:
        self._enqueue("machine", machine)

    def save_model_info(self, meta: dict[str, Any]) -> None:
        self._enqueue("model", meta)

    def sync_users(self, users: list[dict[str, Any]]) -> None:
        self._enqueue("users", users)

    def sync_machines(self, machines: list[dict[str, Any]]) -> None:
        """Insert machines that are missing (never overwrites limits edited by an operator)."""
        self._enqueue("machines_missing", machines)

    # ================================================================== reads (synchronous, failure -> empty)
    def _read(self, sql: str, params: dict | None = None) -> list[dict[str, Any]]:
        if self.state["postgres"] == "unreachable":      # don't stall start-up on a database that is down
            return []
        try:
            with self._pg.connect() as c:
                rows = [dict(r._mapping) for r in c.execute(text(sql), params or {})]
            self._set("postgres", True)
            return rows
        except Exception as exc:
            self._set("postgres", False, str(exc).splitlines()[0])
            return []

    def load_alerts(self, limit: int = 5000) -> list[dict[str, Any]]:
        rows = self._read("SELECT payload FROM alerts ORDER BY id DESC LIMIT :n", {"n": limit})
        return [r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"]) for r in rows]

    def load_maintenance(self) -> list[dict[str, Any]]:
        rows = self._read("SELECT payload FROM maintenance_logs ORDER BY id")
        return [r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"]) for r in rows]

    def load_machines(self) -> list[dict[str, Any]]:
        return self._read("SELECT id, name, kind, ideal_cycle_s, temp_limit, vib_limit FROM machines")

    def query_hourly(self, since: float) -> list[dict[str, Any]]:
        if self._influx is None:
            return super().query_hourly(since)
        flux = f'''
from(bucket: "{self.s.influx_bucket_agg}")
  |> range(start: {int(since)})
  |> filter(fn: (r) => r._measurement == "oee_hourly")
  |> pivot(rowKey: ["_time", "machine_id"], columnKey: ["_field"], valueColumn: "_value")'''
        try:
            tables = self._influx.query_api().query(flux)
            rows = []
            for t in tables:
                for r in t.records:
                    v = r.values
                    rows.append({"machine_id": v["machine_id"], "hour": int(r.get_time().timestamp()),
                                 "planned_s": v.get("planned_s", 0.0), "run_s": v.get("run_s", 0.0),
                                 "ideal_s": v.get("ideal_s", 0.0), "cycles": v.get("cycles", 0.0),
                                 "good": v.get("good", 0.0), "stopped_s": v.get("stopped_s", 0.0)})
            self._set("influx", True)
            return rows
        except Exception as exc:
            self._set("influx", False, str(exc).splitlines()[0])
            return super().query_hourly(since)

    def query_telemetry(self, machine_id: str, t_from: float, t_to: float, max_points: int) -> list[dict[str, Any]] | None:
        if self._influx is None:
            return None
        every = max(1, int((t_to - t_from) / max(max_points, 1)))
        flux = f'''
from(bucket: "{self.s.influx_bucket_raw}")
  |> range(start: {int(t_from)}, stop: {int(t_to) + 1})
  |> filter(fn: (r) => r._measurement == "telemetry" and r.machine_id == "{machine_id}")
  |> filter(fn: (r) => r._field == "temperature" or r._field == "vibration" or r._field == "anomaly_score" or r._field == "cycle_count")
  |> aggregateWindow(every: {every}s, fn: mean, createEmpty: false)
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")'''
        try:
            out = []
            for t in self._influx.query_api().query(flux):
                for r in t.records:
                    v = r.values
                    out.append({"ts": r.get_time().timestamp(), "temperature": v.get("temperature"),
                                "vibration": v.get("vibration"), "status": None,
                                "cycle_count": int(v["cycle_count"]) if v.get("cycle_count") is not None else None,
                                "anomaly_score": v.get("anomaly_score")})
            self._set("influx", True)
            return out
        except Exception as exc:
            self._set("influx", False, str(exc).splitlines()[0])
            return None

    # ================================================================== background writer
    def _run(self) -> None:
        pg_backlog: deque[tuple[str, Any]] = deque(maxlen=20_000)
        hourly_backlog: deque[tuple[str, Any]] = deque(maxlen=2_000)
        points: list[dict[str, Any]] = []
        last_flush = last_probe = time.time()
        while True:
            stopping = self._stop.is_set()
            try:
                kind, payload = self.q.get(timeout=0.4 if not stopping else 0.01)
                if kind == "points":
                    points.extend(payload)
                elif kind in ("hourly", "hourly_missing"):
                    hourly_backlog.append((kind, payload))
                else:
                    pg_backlog.append((kind, payload))
            except queue.Empty:
                if stopping:
                    pass
            now = time.time()
            if pg_backlog and now >= self._pg_next:
                self._drain_pg(pg_backlog)
            if points and (now - last_flush >= 1.0 or len(points) >= 5000 or stopping) and now >= self._influx_next:
                points = self._write_points(points)
                last_flush = now
            if hourly_backlog and now >= self._influx_next:
                try:
                    while hourly_backlog:
                        kind, rows = hourly_backlog[0]
                        self._write_hourly(rows, kind == "hourly_missing")
                        hourly_backlog.popleft()
                    self._set("influx", True)
                except Exception as exc:
                    self._influx_next = time.time() + 5
                    self._set("influx", False, str(exc).splitlines()[0])
            if len(points) > 60_000:               # sink is down for a long time: shed the oldest data
                self.dropped_points += len(points) - 40_000
                points = points[-40_000:]
            if now - last_probe > 10:
                last_probe = now
                self._probe()
            if stopping and self.q.empty():
                if pg_backlog and now >= self._pg_next:
                    self._drain_pg(pg_backlog)
                return

    # ---- PostgreSQL
    def _drain_pg(self, backlog: deque) -> None:
        try:
            with self._pg.begin() as c:
                n = 0
                while backlog and n < 500:
                    kind, payload = backlog[0]
                    self._exec_pg(c, kind, payload)
                    backlog.popleft()
                    n += 1
            self._pg_fail = 0
            self._set("postgres", True)
        except Exception as exc:
            self._pg_fail += 1
            self._pg_next = time.time() + PG_BACKOFF[min(self._pg_fail - 1, len(PG_BACKOFF) - 1)]
            self._set("postgres", False, str(exc).splitlines()[0])
            if self._pg_fail in (1, 5):
                log.warning("PostgreSQL write failed (%s) - %d item(s) queued, retrying", str(exc).splitlines()[0], len(backlog))
            # a poisoned item (e.g. constraint error) must not block everything forever
            if self._pg_fail >= 6 and backlog:
                bad = backlog.popleft()
                log.error("dropping un-writable %s record after repeated failures", bad[0])
                self._pg_fail = 3

    def _exec_pg(self, c, kind: str, p: Any) -> None:
        if kind == "alert":
            c.execute(text("""
                INSERT INTO alerts (id, machine_id, level, kind, status, active, title, message, value, threshold, eta_s, score,
                                    opened_at, cleared_at, acked_by, acked_at, technician, resolved_by, resolved_at,
                                    resolution_notes, payload, updated_at)
                VALUES (:id, :machine_id, :level, :kind, :status, :active, :title, :message, :value, :threshold, :eta_s, :score,
                        :opened_at, :cleared_at, :acked_by, :acked_at, :technician, :resolved_by, :resolved_at,
                        :resolution_notes, CAST(:payload AS JSONB), now())
                ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status, active = EXCLUDED.active, message = EXCLUDED.message,
                    value = EXCLUDED.value, eta_s = EXCLUDED.eta_s, score = EXCLUDED.score, cleared_at = EXCLUDED.cleared_at,
                    acked_by = EXCLUDED.acked_by, acked_at = EXCLUDED.acked_at, technician = EXCLUDED.technician,
                    resolved_by = EXCLUDED.resolved_by, resolved_at = EXCLUDED.resolved_at,
                    resolution_notes = EXCLUDED.resolution_notes, payload = EXCLUDED.payload, updated_at = now()"""),
                {**{k: p.get(k) for k in ("id", "machine_id", "level", "kind", "status", "active", "title", "message", "value",
                                          "threshold", "eta_s", "score", "acked_by", "technician", "resolved_by", "resolution_notes")},
                 "opened_at": _dt(p["opened_at"]), "cleared_at": _dt(p.get("cleared_at")), "acked_at": _dt(p.get("acked_at")),
                 "resolved_at": _dt(p.get("resolved_at")), "payload": json.dumps(p, default=str)})
            fb = p.get("feedback")
            if fb:
                c.execute(text("""
                    INSERT INTO feedback (alert_id, verdict, given_by, comment, created_at)
                    VALUES (:a, :v, :b, :c, :t)
                    ON CONFLICT (alert_id) DO UPDATE SET verdict = EXCLUDED.verdict, given_by = EXCLUDED.given_by,
                        comment = EXCLUDED.comment, created_at = EXCLUDED.created_at"""),
                          {"a": p["id"], "v": fb["verdict"], "b": fb.get("by"), "c": fb.get("comment"), "t": _dt(fb.get("at"))})
        elif kind == "maint":
            c.execute(text("""
                INSERT INTO maintenance_logs (id, machine_id, alert_id, action, notes, technician, status, created_by,
                                              created_at, updated_at, payload)
                VALUES (:id, :machine_id, :alert_id, :action, :notes, :technician, :status, :created_by, :created_at,
                        :updated_at, CAST(:payload AS JSONB))
                ON CONFLICT (id) DO UPDATE SET action = EXCLUDED.action, notes = EXCLUDED.notes,
                    technician = EXCLUDED.technician, status = EXCLUDED.status, updated_at = EXCLUDED.updated_at,
                    payload = EXCLUDED.payload"""),
                      {**{k: p.get(k) for k in ("id", "machine_id", "alert_id", "action", "notes", "technician", "status", "created_by")},
                       "created_at": _dt(p["created_at"]), "updated_at": _dt(p["updated_at"]),
                       "payload": json.dumps(p, default=str)})
        elif kind == "maint_del":
            c.execute(text("DELETE FROM maintenance_logs WHERE id = :id"), {"id": p})
        elif kind == "machine":
            c.execute(text("""
                INSERT INTO machines (id, name, kind, ideal_cycle_s, temp_limit, vib_limit)
                VALUES (:id, :name, :kind, :ideal_cycle_s, :temp_limit, :vib_limit)
                ON CONFLICT (id) DO UPDATE SET temp_limit = EXCLUDED.temp_limit, vib_limit = EXCLUDED.vib_limit,
                    updated_at = now()"""), p)
        elif kind == "machines_missing":
            for m in p:
                c.execute(text("""
                    INSERT INTO machines (id, name, kind, ideal_cycle_s, temp_limit, vib_limit)
                    VALUES (:id, :name, :kind, :ideal_cycle_s, :temp_limit, :vib_limit)
                    ON CONFLICT (id) DO NOTHING"""), {k: m[k] for k in ("id", "name", "kind", "ideal_cycle_s", "temp_limit", "vib_limit")})
        elif kind == "users":
            for u in p:
                c.execute(text("""
                    INSERT INTO users (username, role, password_hash) VALUES (:username, :role, :password_hash)
                    ON CONFLICT (username) DO UPDATE SET role = EXCLUDED.role, password_hash = EXCLUDED.password_hash"""), u)
        elif kind == "model":
            c.execute(text("""
                INSERT INTO ml_models (algorithm, trained_at, threshold, metrics)
                VALUES (:a, CAST(:t AS TIMESTAMPTZ), :th, CAST(:m AS JSONB)) ON CONFLICT DO NOTHING"""),
                      {"a": p.get("algorithm", "IsolationForest"), "t": p.get("trained_at"), "th": p.get("threshold_pct"),
                       "m": json.dumps(p.get("validation") or {}, default=str)})
        else:
            log.error("unknown storage record kind %r", kind)

    # ---- InfluxDB
    def _write_points(self, points: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Write a batch; returns the points to retry (empty on success)."""
        if self._write_api is None:
            return []
        from influxdb_client import Point, WritePrecision

        try:
            pts = []
            for d in points:
                pts.append(Point("telemetry").tag("machine_id", d["machine_id"])
                           .field("temperature", float(d["temperature"])).field("vibration", float(d["vibration"]))
                           .field("status", d["status"]).field("cycle_count", int(d["cycle_count"]))
                           .field("anomaly_score", float(d["anomaly_score"]))
                           .time(int(d["ts"] * 1000), WritePrecision.MS))
            if pts:
                self._write_api.write(bucket=self.s.influx_bucket_raw, org=self.s.influx_org, record=pts)
            self._set("influx", True)
            return []
        except Exception as exc:
            self._influx_next = time.time() + 5
            self._set("influx", False, str(exc).splitlines()[0])
            return points

    def _write_hourly(self, rows: list[dict[str, Any]], only_missing: bool) -> None:
        from influxdb_client import Point, WritePrecision

        if self._write_api is None or not rows:
            return
        if only_missing:
            have = {(r["machine_id"], r["hour"]) for r in self.query_hourly(min(r["hour"] for r in rows) - 1)}
            rows = [r for r in rows if (r["machine_id"], r["hour"]) not in have]
        pts = [Point("oee_hourly").tag("machine_id", r["machine_id"])
               .field("planned_s", float(r["planned_s"])).field("run_s", float(r["run_s"])).field("ideal_s", float(r["ideal_s"]))
               .field("cycles", float(r["cycles"])).field("good", float(r["good"])).field("stopped_s", float(r["stopped_s"]))
               .time(int(r["hour"]), WritePrecision.S) for r in rows]
        if pts:
            self._write_api.write(bucket=self.s.influx_bucket_agg, org=self.s.influx_org, record=pts)
