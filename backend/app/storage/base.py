"""Storage abstraction. ``STORAGE_MODE=memory`` (default) needs no database at all; ``db`` adds
InfluxDB v2 (time series) + PostgreSQL (metadata) behind the very same interface.

The live engine always keeps its hot state in memory; the repository is the durable side:
write-through for alerts / maintenance / telemetry and read-back at start-up and for history.
Every method is synchronous and thread-safe; ``DbRepository`` never blocks the 500 ms loop
(writes are queued) and never raises into callers (failures are logged and retried).
"""
from __future__ import annotations

import threading
from typing import Any


class Repository:
    mode = "memory"

    def __init__(self) -> None:
        self._hourly: dict[tuple[str, int], dict[str, Any]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None: ...

    def stop(self) -> None: ...

    def health(self) -> dict[str, Any]:
        return {"storage_mode": "memory", "influx": "disabled", "postgres": "disabled", "queue": 0}

    # ------------------------------------------------------------------ time series
    def write_telemetry(self, points: list[dict[str, Any]]) -> None:
        """Full-rate telemetry (machine_id, ts, temperature, vibration, status, cycle_count, anomaly_score)."""

    def query_telemetry(self, machine_id: str, t_from: float, t_to: float, max_points: int) -> list[dict[str, Any]] | None:
        """Return history from durable storage, or ``None`` when only the in-memory buffers apply."""
        return None

    # ------------------------------------------------------------------ hourly OEE rollups (reports)
    def upsert_hourly(self, rows: list[dict[str, Any]], only_missing: bool = False) -> None:
        with self._lock:
            for r in rows:
                key = (r["machine_id"], int(r["hour"]))
                if only_missing and key in self._hourly:
                    continue
                self._hourly[key] = r

    def query_hourly(self, since: float) -> list[dict[str, Any]]:
        with self._lock:
            return [r for (m, h), r in self._hourly.items() if h >= since]

    # ------------------------------------------------------------------ relational records
    def save_alert(self, alert: dict[str, Any]) -> None: ...

    def load_alerts(self, limit: int = 5000) -> list[dict[str, Any]]:
        return []

    def save_maintenance(self, rec: dict[str, Any]) -> None: ...

    def delete_maintenance(self, rec_id: int) -> None: ...

    def load_maintenance(self) -> list[dict[str, Any]]:
        return []

    def save_machine(self, machine: dict[str, Any]) -> None: ...

    def load_machines(self) -> list[dict[str, Any]]:
        return []

    def sync_users(self, users: list[dict[str, Any]]) -> None: ...

    def save_model_info(self, meta: dict[str, Any]) -> None: ...


def create_repository(settings) -> Repository:
    if settings.storage_mode.lower() == "db":
        from .db import DbRepository

        return DbRepository(settings)
    return Repository()
