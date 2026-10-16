"""DbRepository logic tested against fake PostgreSQL / InfluxDB clients (no servers needed).

These tests prove the queueing, retry/back-off, batching and idempotent hourly write logic. They do NOT replace
`python -m app.storage.verify` against your real databases (see docs/DB_SETUP_STEP_BY_STEP.md).
"""
import json
import time
from collections import deque
from contextlib import contextmanager

import pytest

from app.config import Settings
from app.storage.db import DbRepository


class FakeConn:
    def __init__(self, log, fail):
        self.log, self.fail = log, fail

    def execute(self, stmt, params=None):
        if self.fail["on"]:
            raise RuntimeError("connection refused")
        self.log.append((" ".join(str(stmt).split()), params or {}))

        class R:
            def __iter__(self_inner):
                return iter([])

            def scalar(self_inner):
                return 1

        return R()


class FakePG:
    def __init__(self):
        self.log, self.fail = [], {"on": False}

    @contextmanager
    def begin(self):
        yield FakeConn(self.log, self.fail)

    connect = begin

    def dispose(self):
        pass


class FakeWriteApi:
    def __init__(self):
        self.writes, self.fail = [], False

    def write(self, bucket, org, record):
        if self.fail:
            raise RuntimeError("influx down")
        self.writes.append((bucket, org, list(record)))


class FakeInflux:
    def ping(self):
        return True

    def close(self):
        pass


@pytest.fixture
def repo():
    # explicit values so the test never depends on the developer's own .env (cloud org, bucket names, ...)
    r = DbRepository(Settings(storage_mode="db", influx_token="t", influx_url="http://localhost:8086", influx_org="oee-org",
                              influx_bucket_raw="telemetry_raw", influx_bucket_agg="telemetry_agg"))
    r._pg, r._influx, r._write_api = FakePG(), FakeInflux(), FakeWriteApi()
    return r


ALERT = {"id": 7, "machine_id": "CNC-01", "level": "red", "kind": "temp_high", "status": "open", "active": True, "title": "t",
         "message": "m", "value": 86.0, "threshold": 85.0, "eta_s": None, "score": None, "opened_at": 1_700_000_000.0,
         "cleared_at": None, "acked_by": None, "acked_at": None, "technician": None, "resolved_by": None,
         "resolved_at": None, "resolution_notes": None, "feedback": {"verdict": "true_positive", "by": "bob", "at": 1.0, "comment": "ok"}}


def test_alert_upsert_and_feedback_rows(repo):
    backlog = deque([("alert", ALERT)])
    repo._drain_pg(backlog)
    assert not backlog and repo.state["postgres"] == "ok"
    sql = [s for s, _ in repo._pg.log]
    assert any(s.startswith("INSERT INTO alerts") and "ON CONFLICT (id) DO UPDATE" in s for s in sql)
    assert any(s.startswith("INSERT INTO feedback") for s in sql)
    params = next(p for s, p in repo._pg.log if s.startswith("INSERT INTO alerts"))
    assert params["id"] == 7 and json.loads(params["payload"])["machine_id"] == "CNC-01"
    assert params["opened_at"].year == 2023       # epoch seconds converted to timestamptz


def test_postgres_outage_keeps_items_and_recovers(repo):
    repo._pg.fail["on"] = True
    backlog = deque([("alert", ALERT), ("maint_del", 3)])
    repo._drain_pg(backlog)
    assert len(backlog) == 2 and repo.state["postgres"] == "unreachable" and repo._pg_next > time.time()
    repo._pg.fail["on"] = False
    repo._pg_next = 0
    repo._drain_pg(backlog)
    assert not backlog and repo.state["postgres"] == "ok"


def test_telemetry_batch_written_and_retained_on_failure(repo):
    pts = [{"machine_id": "CNC-01", "ts": 1_700_000_000.0 + i, "temperature": 61.5, "vibration": 2.1, "status": "RUNNING",
            "cycle_count": 10 + i, "anomaly_score": 4.0} for i in range(5)]
    assert repo._write_points(pts) == []
    bucket, org, rec = repo._write_api.writes[0]
    assert bucket == "telemetry_raw" and org == "oee-org" and len(rec) == 5
    line = rec[0].to_line_protocol()
    assert line.startswith("telemetry,machine_id=CNC-01") and "temperature=61.5" in line and 'status="RUNNING"' in line and "cycle_count=10i" in line
    repo._write_api.fail = True
    assert repo._write_points(pts) == pts          # kept for retry
    assert repo.state["influx"] == "unreachable" and repo._influx_next > time.time()


def test_hourly_rollup_uses_aggregated_bucket_and_skips_existing(repo, monkeypatch):
    rows = [{"machine_id": "CNC-01", "hour": 1_700_000_000 + 3600 * i, "planned_s": 3600.0, "run_s": 3400.0, "ideal_s": 3000.0,
             "cycles": 250.0, "good": 245.0, "stopped_s": 0.0} for i in range(3)]
    repo._write_hourly(rows, only_missing=False)
    bucket, _, rec = repo._write_api.writes[-1]
    assert bucket == "telemetry_agg" and len(rec) == 3 and rec[0].to_line_protocol().startswith("oee_hourly,machine_id=CNC-01")
    monkeypatch.setattr(repo, "query_hourly", lambda since: [rows[0], rows[1]])   # two hours already persisted
    repo._write_hourly(rows, only_missing=True)
    assert len(repo._write_api.writes[-1][2]) == 1


def test_health_reports_each_database_separately(repo):
    repo.state.update(influx="ok", postgres="unreachable")
    repo.last_error["postgres"] = "boom"
    h = repo.health()
    assert h["storage_mode"] == "db" and h["influx"] == "ok" and h["postgres"] == "unreachable" and "postgres" in h["last_error"]


def test_reads_return_empty_when_postgres_down(repo):
    repo.state["postgres"] = "unreachable"
    assert repo.load_alerts() == [] and repo.load_maintenance() == [] and repo.load_machines() == []


def test_full_thread_roundtrip(repo):
    repo._thread = None
    import threading

    t = threading.Thread(target=repo._run, daemon=True)
    t.start()
    repo.save_alert(ALERT)
    repo.write_telemetry([{"machine_id": "CNC-01", "ts": time.time(), "temperature": 60.0, "vibration": 2.0, "status": "IDLE",
                           "cycle_count": 1, "anomaly_score": 0.0}])
    deadline = time.time() + 5
    while time.time() < deadline and not (repo._write_api.writes and repo._pg.log):
        time.sleep(0.1)
    repo._stop.set()
    t.join(5)
    assert repo._write_api.writes and any(s.startswith("INSERT INTO alerts") for s, _ in repo._pg.log)
