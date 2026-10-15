"""The real-time engine: ingest -> OEE / rules (per sample), then a 500 ms tick that runs the ML
batch, What-If projection, alert state machine and builds the snapshot pushed to the dashboard.

Everything here runs on the asyncio loop thread (MQTT callbacks hop onto it), so no locking is
needed. Heavy / blocking work (DB writes, back-fill) lives elsewhere.
"""
from __future__ import annotations

import logging
import statistics
import time
from collections import deque
from datetime import datetime
from typing import Any

import numpy as np
from pydantic import ValidationError

from .config import Settings
from .ml.features import StreamFeatures
from .ml.scorer import AnomalyScorer
from .schemas import TelemetryIn
from .services import whatif
from .services.alerts import LEVEL_RANK, Alert, AlertManager
from .services.oee import MachineOEE, plant_oee
from .services.rules import Condition, evaluate_rules
from .storage.base import Repository

log = logging.getLogger("engine")

STATUS_CODE = {"RUNNING": 0, "IDLE": 1, "STOPPED": 2}
CODE_STATUS = {v: k for k, v in STATUS_CODE.items()}
ONLINE_WITHIN_S = 3.0
COARSE_EVERY_S = 5.0
SHIFTS = (("A", 6, 14), ("B", 14, 22), ("C", 22, 6))


def shift_of(hour_local: int) -> str:
    return "A" if 6 <= hour_local < 14 else "B" if 14 <= hour_local < 22 else "C"


class MachineState:
    def __init__(self, profile, settings: Settings):
        self.profile = profile
        self.id = profile.id
        self.temp_limit = profile.temp_limit
        self.vib_limit = profile.vib_limit
        self.oee = MachineOEE(profile.ideal_cycle_s)
        self.feats = StreamFeatures(profile.base_temp, profile.base_vib, profile.temp_scale, profile.vib_scale,
                                    profile.vib_noise)
        self.latest: dict | None = None
        self.fresh = False
        self.last_rx = 0.0
        self.fine: deque[list] = deque(maxlen=2400)           # ~20 min @ 500 ms
        self.coarse: deque[list] = deque(maxlen=5900)         # ~8 h   @ 5 s
        self._last_coarse = 0.0
        self.whatif_buf: deque[tuple[float, float]] = deque(maxlen=settings.whatif_window_s + 5)
        self._last_whatif_s = -1
        self.cyc_hist: deque[tuple[float, int, int]] = deque(maxlen=75)
        self._last_cyc_s = -1
        self.score = 0.0
        self.ml_ok = True
        self.red: list[Condition] = []
        self.projection: dict = {"ready": False, "projected": False}
        self.level = "green"
        self.top_alert: Alert | None = None

    def thresholds(self) -> dict[str, float]:
        return {"temp_limit": self.temp_limit, "vib_limit": self.vib_limit}


class Engine:
    def __init__(self, settings: Settings, repo: Repository, scorer: AnomalyScorer, profiles: list):
        self.s = settings
        self.repo = repo
        self.scorer = scorer
        self.machines: dict[str, MachineState] = {p.id: MachineState(p, settings) for p in profiles}
        self.alerts = AlertManager(self._on_alert_event)
        self.maintenance: dict[int, dict] = {}
        self._next_maint = 1
        self.events: list[dict] = []
        self.started = time.time()
        self.seq = 0
        self.stats = {"rx": 0, "invalid": 0, "unknown_machine": 0, "ticks": 0, "ml_errors": 0}
        self.latency_ms: deque[float] = deque(maxlen=600)
        self.tick_ms: deque[float] = deque(maxlen=600)
        self.infer_ms: deque[float] = deque(maxlen=600)
        self.db_batch: list[list] = []
        self._last_flush = 0.0
        self._last_hourly_flush = 0.0
        self.backfill_until_hour = 0
        self.backfill_info: dict[str, Any] = {"days": 0, "seconds": 0.0}
        self.sim_status: dict[str, Any] = {}
        self.mqtt_status: dict[str, Any] = {"enabled": settings.ingest_mode == "mqtt", "connected": None}

    # ================================================================== persistence hooks
    def load_persisted(self) -> None:
        try:
            self.alerts.load(self.repo.load_alerts())
            for rec in self.repo.load_maintenance():
                self.maintenance[rec["id"]] = rec
                self._next_maint = max(self._next_maint, rec["id"] + 1)
            for row in self.repo.load_machines():
                ms = self.machines.get(row["id"])
                if ms:
                    ms.temp_limit = float(row.get("temp_limit", ms.temp_limit))
                    ms.vib_limit = float(row.get("vib_limit", ms.vib_limit))
        except Exception:
            log.exception("could not load persisted records - continuing with empty state")

    def _on_alert_event(self, event: str, alert: Alert) -> None:
        d = alert.to_dict()
        self.events.append({"type": "alert_event", "event": event, "alert": d})
        try:
            self.repo.save_alert(d)
        except Exception:
            log.exception("repo.save_alert failed")
        if event == "opened":
            log.info("ALERT #%s %s %s %s: %s", alert.id, alert.level.upper(), alert.machine_id, alert.kind, alert.message)

    # ================================================================== ingest
    def ingest(self, raw: dict) -> tuple[bool, str | None]:
        try:
            m = TelemetryIn.model_validate(raw)
        except ValidationError as exc:
            self.stats["invalid"] += 1
            msg = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
            log.warning("rejected telemetry: %s | payload=%.200s", msg, raw)
            return False, msg
        ms = self.machines.get(m.machine_id)
        if ms is None:
            self.stats["unknown_machine"] += 1
            return False, f"unknown machine {m.machine_id}"
        now = time.time()
        ts = m.ts if m.ts is not None and abs(m.ts - now) < 86400 * 365 else now
        if ts > now + 5:
            ts = now
        s = {"machine_id": m.machine_id, "ts": ts, "temperature": m.temperature, "vibration": m.vibration,
             "status": m.status, "cycle_count": m.cycle_count,
             "good_count": m.good_count if m.good_count is not None else m.cycle_count}
        self.stats["rx"] += 1
        ms.latest, ms.fresh, ms.last_rx = s, True, now
        running = m.status == "RUNNING"
        ms.oee.update(ts, m.status, s["cycle_count"], s["good_count"])
        ms.feats.push(ts, m.temperature, m.vibration, running)
        entry = [ts, m.temperature, m.vibration, STATUS_CODE[m.status], m.cycle_count, None, m.machine_id]
        ms.fine.append(entry)
        self.db_batch.append(entry)
        if len(self.db_batch) > 40000:
            del self.db_batch[:10000]
        if ts - ms._last_coarse >= COARSE_EVERY_S:
            ms._last_coarse = ts
            ms.coarse.append(entry)
        sec = int(ts)
        if running and sec != ms._last_whatif_s:
            ms._last_whatif_s = sec
            ms.whatif_buf.append((ts, m.temperature))
        if sec != ms._last_cyc_s:
            ms._last_cyc_s = sec
            ms.cyc_hist.append((ts, s["cycle_count"], s["good_count"]))
        ms.red = evaluate_rules(ms.temp_limit, ms.vib_limit, m.temperature, m.vibration, m.status, ms.profile.name)
        return True, None

    # ================================================================== tick
    def tick(self) -> dict:
        t0 = time.perf_counter()
        now = time.time()
        self.seq += 1
        self.stats["ticks"] += 1
        thr = self.s.anomaly_threshold

        # ---- 1. batched ML inference (one call for every machine with a fresh, clean RUNNING window)
        batch, who = [], []
        for ms in self.machines.values():
            if ms.latest is None:
                continue
            if ms.fresh and ms.latest["status"] == "RUNNING" and ms.feats.clean:
                batch.append(ms.feats.vector(ms.latest["temperature"], ms.latest["vibration"]))
                who.append(ms)
            elif ms.fresh and ms.ml_ok:
                ms.score *= 0.8             # idle / stopped / warming up: nothing to score, decay
        if batch:
            try:
                pct = self.scorer.score(np.asarray(batch, dtype=float))
                self.infer_ms.append(self.scorer.last_ms)
                for ms, p in zip(who, pct):
                    ms.score, ms.ml_ok = float(p), True
            except Exception as exc:        # NFR-R1: keep the last known score, rules keep working
                self.stats["ml_errors"] += 1
                if all(ms.ml_ok for ms in who):
                    log.error("ML scoring unavailable (%s) - holding last known scores", exc)
                for ms in who:
                    ms.ml_ok = False
        elif self.scorer.outage or not self.scorer.ready:
            for ms in self.machines.values():
                ms.ml_ok = False
        else:
            for ms in self.machines.values():
                ms.ml_ok = True

        # ---- 2. per machine: What-If projection, conditions, alerts
        snap_machines = []
        for ms in self.machines.values():
            s = ms.latest
            online = s is not None and (now - ms.last_rx) < ONLINE_WITHIN_S
            if s is not None and ms.fresh:
                ms.fine[-1][5] = round(ms.score, 1)
                lat = (now - s["ts"]) * 1000.0
                if 0 <= lat < 60000:
                    self.latency_ms.append(lat)
            if s is not None and online:
                ms.projection = whatif.project(
                    list(ms.whatif_buf), s["ts"], ms.temp_limit, horizon_s=self.s.whatif_horizon_s,
                    min_slope=self.s.whatif_min_slope, min_r2=self.s.whatif_min_r2,
                    min_points=self.s.whatif_min_points)
                conds = list(ms.red)
                p = ms.projection
                if p.get("projected") and not ms.red:
                    conds.append(Condition(
                        "projected_fault", "orange", "Projected fault",
                        f"Temperature trending {p['slope_c_per_min']:+.1f} °C/min - projected to reach "
                        f"{ms.temp_limit:.0f} °C in {p['eta_s']:.0f} s", s["temperature"], ms.temp_limit))
                if ms.score > thr and s["status"] == "RUNNING":
                    conds.append(Condition("ml_anomaly", "yellow", "ML anomaly caution",
                                           f"Isolation Forest anomaly score {ms.score:.0f} % (> {thr:.0f} %)",
                                           ms.score, thr))
                ms.level = self.alerts.update(ms.id, conds, now)
                # keep eta / score on the live alert
                for kind, tr in ((k, t) for (m, k), t in self.alerts._tracks.items() if m == ms.id):
                    if tr.alert_id is not None:
                        a = self.alerts.alerts[tr.alert_id]
                        if kind == "projected_fault":
                            a.eta_s = p.get("eta_s")
                        elif kind == "ml_anomaly":
                            a.score = round(max(a.score or 0.0, ms.score), 1)
            ms.fresh = False
            ms.top_alert = self._top_alert(ms.id)
            snap_machines.append(self._machine_snapshot(ms, now, online))

        # ---- 3. plant KPIs
        online_states = [m for m in snap_machines if m["online"]]
        throughput = 0.0
        for ms in self.machines.values():
            if len(ms.cyc_hist) >= 2:
                a, b = ms.cyc_hist[0], ms.cyc_hist[-1]
                if b[0] - a[0] >= 5:
                    throughput += (b[2] - a[2]) / (b[0] - a[0]) * 60.0
        levels = {lv: sum(1 for m in snap_machines if m["level"] == lv) for lv in LEVEL_RANK}
        snap = {
            "type": "snapshot", "seq": self.seq, "ts": now, "machines": snap_machines,
            "plant": {
                "oee": plant_oee([m.oee for m in self.machines.values()]),
                "machines_total": len(self.machines),
                "active_machines": sum(1 for m in online_states if m["status"] == "RUNNING"),
                "online_machines": len(online_states),
                "open_alerts": self.alerts.active_count(),
                "avg_anomaly": round(statistics.fmean([m["anomaly_score"] for m in online_states]), 1) if online_states else 0.0,
                "throughput_per_min": round(throughput, 1),
                "levels": levels,
            },
            "ml_ok": all(m["ml_ok"] for m in snap_machines) if snap_machines else True,
        }
        self.tick_ms.append((time.perf_counter() - t0) * 1000.0)
        if now - self._last_hourly_flush > 30:
            self._last_hourly_flush = now
            self.flush_hourly()
        return snap

    def _top_alert(self, machine_id: str) -> Alert | None:
        best = None
        for (m, _k), tr in self.alerts._tracks.items():
            if m == machine_id and tr.alert_id is not None:
                a = self.alerts.alerts[tr.alert_id]
                if best is None or LEVEL_RANK[a.level] > LEVEL_RANK[best.level]:
                    best = a
        return best

    def _machine_snapshot(self, ms: MachineState, now: float, online: bool) -> dict:
        s = ms.latest or {}
        p = ms.projection
        wi = {"ready": p.get("ready", False), "projected": p.get("projected", False), "eta_s": p.get("eta_s"),
              "slope_c_per_min": p.get("slope_c_per_min", 0.0), "r2": p.get("r2", 0.0), "fit_now": p.get("fit_now")}
        a = ms.top_alert
        return {
            "id": ms.id, "name": ms.profile.name, "kind": ms.profile.kind, "online": online,
            "status": s.get("status", "UNKNOWN"), "temperature": s.get("temperature"),
            "vibration": s.get("vibration"), "cycle_count": s.get("cycle_count"), "good_count": s.get("good_count"),
            "ts": s.get("ts"), "age_ms": int((now - ms.last_rx) * 1000) if ms.last_rx else None,
            "anomaly_score": round(ms.score, 1), "ml_ok": ms.ml_ok, "level": ms.level if online or ms.latest else "green",
            "reason": a.title if a else None, "alert_id": a.id if a else None,
            "alert_status": a.status if a else None,
            "whatif": wi, "thresholds": ms.thresholds(), "oee": ms.oee.result(),
        }

    # ================================================================== helpers for the API
    def set_thresholds(self, machine_id: str, temp_limit: float | None, vib_limit: float | None) -> dict:
        ms = self.machines[machine_id]
        if temp_limit is not None:
            ms.temp_limit = float(temp_limit)
        if vib_limit is not None:
            ms.vib_limit = float(vib_limit)
        row = {"id": ms.id, "name": ms.profile.name, "kind": ms.profile.kind, **ms.thresholds(),
               "ideal_cycle_s": ms.profile.ideal_cycle_s}
        self.repo.save_machine(row)
        return row

    def machine_info(self) -> list[dict]:
        out = []
        for ms in self.machines.values():
            p = ms.profile
            out.append({"id": ms.id, "name": p.name, "kind": p.kind, "ideal_cycle_s": p.ideal_cycle_s,
                        "temp_limit": ms.temp_limit, "vib_limit": ms.vib_limit, "base_temp": p.base_temp,
                        "base_vib": p.base_vib, "reject_rate": p.reject_rate})
        return out

    def telemetry(self, machine_id: str, t_from: float, t_to: float, max_points: int = 1200) -> dict:
        ms = self.machines[machine_id]
        fine0 = ms.fine[0][0] if ms.fine else float("inf")
        if t_from >= fine0 or not ms.coarse:
            src, res = ms.fine, "500ms"
        else:
            src, res = ms.coarse, "5s"
        rows = [e for e in src if t_from <= e[0] <= t_to]
        stride = max(1, -(-len(rows) // max_points))
        rows = rows[::stride]
        pts = [{"ts": e[0], "temperature": e[1], "vibration": e[2], "status": CODE_STATUS[e[3]],
                "cycle_count": e[4], "anomaly_score": e[5]} for e in rows]
        covered_from = ms.coarse[0][0] if ms.coarse else fine0
        return {"machine_id": machine_id, "resolution": res, "points": pts, "memory_covers_from": covered_from}

    def whatif_detail(self, machine_id: str) -> dict:
        ms = self.machines[machine_id]
        buf = list(ms.whatif_buf)
        now = ms.latest["ts"] if ms.latest else time.time()
        p = whatif.project(buf, now, ms.temp_limit, horizon_s=self.s.whatif_horizon_s,
                           min_slope=self.s.whatif_min_slope, min_r2=self.s.whatif_min_r2,
                           min_points=self.s.whatif_min_points)
        line = []
        if p["ready"]:
            t0 = p["t0"]
            for t in (buf[0][0], now, now + self.s.whatif_horizon_s):
                line.append({"ts": t, "y": round(p["slope_c_per_s"] * (t - t0) + p["intercept"], 2)})
        step = max(1, len(buf) // 120)
        return {"machine_id": machine_id, "equation": "y = m·x + c", "window_s": self.s.whatif_window_s,
                "threshold": ms.temp_limit, "horizon_s": self.s.whatif_horizon_s, "projection": p, "line": line,
                "points": [{"ts": t, "temperature": y} for t, y in buf[::step]],
                "now_fit": p.get("fit_now"), "level": ms.level}

    # ------------------------------------------------------------------ maintenance
    def add_maintenance(self, data: dict, user: str) -> dict:
        rid = self._next_maint
        self._next_maint += 1
        now = time.time()
        rec = {"id": rid, **data, "created_by": user, "created_at": now, "updated_at": now}
        self.maintenance[rid] = rec
        self.repo.save_maintenance(rec)
        self.events.append({"type": "maintenance_event", "event": "created", "record": rec})
        return rec

    def patch_maintenance(self, rid: int, patch: dict) -> dict:
        rec = self.maintenance[rid]
        rec.update({k: v for k, v in patch.items() if v is not None})
        rec["updated_at"] = time.time()
        self.repo.save_maintenance(rec)
        self.events.append({"type": "maintenance_event", "event": "updated", "record": rec})
        return rec

    def delete_maintenance(self, rid: int) -> None:
        del self.maintenance[rid]
        self.repo.delete_maintenance(rid)
        self.events.append({"type": "maintenance_event", "event": "deleted", "record": {"id": rid}})

    # ------------------------------------------------------------------ reports (FR-08)
    def hourly_rows(self, since: float, repo_rows: list[dict] | None = None) -> dict[tuple[str, int], list[float]]:
        rows: dict[tuple[str, int], list[float]] = {}
        for ms in self.machines.values():
            for hour, v in ms.oee.hourly.items():
                if hour >= since:
                    rows[(ms.id, hour)] = list(v)
        for r in repo_rows or []:   # persisted hours are authoritative for completed history
            if r["machine_id"] in self.machines and r["hour"] < self.backfill_until_hour:
                rows[(r["machine_id"], r["hour"])] = [r["planned_s"], r["run_s"], r["ideal_s"], r["cycles"],
                                                      r["good"], r["stopped_s"]]
        return rows

    def flush_hourly(self) -> None:
        batch_old, batch_new = [], []
        for ms in self.machines.values():
            for hour in list(ms.oee.dirty_hours):
                v = ms.oee.hourly[hour]
                row = {"machine_id": ms.id, "hour": hour, "planned_s": v[0], "run_s": v[1], "ideal_s": v[2],
                       "cycles": v[3], "good": v[4], "stopped_s": v[5]}
                (batch_old if hour < self.backfill_until_hour else batch_new).append(row)
            ms.oee.dirty_hours.clear()
        try:
            if batch_old:
                self.repo.upsert_hourly(batch_old, only_missing=True)
            if batch_new:
                self.repo.upsert_hourly(batch_new)
        except Exception:
            log.exception("flush_hourly failed")

    def flush_telemetry(self) -> None:
        if not self.db_batch:
            return
        batch, self.db_batch = self.db_batch, []
        pts = [{"ts": e[0], "temperature": e[1], "vibration": e[2], "status": CODE_STATUS[e[3]], "cycle_count": e[4],
                "anomaly_score": e[5] if e[5] is not None else 0.0, "machine_id": e[6]} for e in batch]
        try:
            self.repo.write_telemetry(pts)
        except Exception:
            log.exception("write_telemetry failed")

    def report_oee_trend(self, days: int, repo_rows: list[dict] | None = None) -> dict:
        now = time.time()
        since = (int(now // 86400) - days + 1) * 86400
        rows = self.hourly_rows(since - 86400, repo_rows)
        per_day: dict[str, dict] = {}
        for (mid, hour), v in rows.items():
            day = datetime.fromtimestamp(hour).strftime("%Y-%m-%d")
            d = per_day.setdefault(day, {"total": [0.0] * 6, "machines": {}})
            m = d["machines"].setdefault(mid, [0.0] * 6)
            for i in range(6):
                d["total"][i] += v[i]
                m[i] += v[i]
        from .services.oee import compute_oee

        out = []
        for day in sorted(per_day)[-days:]:
            d = per_day[day]
            o = compute_oee(d["total"])
            out.append({"date": day, **{k: o[k] for k in ("oee", "availability", "performance", "quality")},
                        "by_machine": {mid: compute_oee(v)["oee"] for mid, v in sorted(d["machines"].items())}})
        return {"days": days, "series": out, "timezone": time.strftime("%Z"),
                "note": "Includes simulated history back-fill" if self.backfill_info.get("days") else None}

    def report_downtime(self, days: int, repo_rows: list[dict] | None = None) -> dict:
        now = time.time()
        since = (int(now // 86400) - days + 1) * 86400
        rows = self.hourly_rows(since - 86400, repo_rows)
        cell: dict[tuple[str, str], dict] = {}
        for (mid, hour), v in rows.items():
            dt_ = datetime.fromtimestamp(hour)
            shift = shift_of(dt_.hour)
            day = dt_.strftime("%Y-%m-%d")
            if shift == "C" and dt_.hour < 6:
                day = datetime.fromtimestamp(hour - 86400).strftime("%Y-%m-%d")   # night shift belongs to the day it started
            c = cell.setdefault((day, shift), {"planned": 0.0, "run": 0.0, "stopped": 0.0, "by": {}})
            c["planned"] += v[0]; c["run"] += v[1]; c["stopped"] += v[5]
            c["by"][mid] = c["by"].get(mid, 0.0) + (v[0] - v[1])
        days_sorted = sorted({d for d, _ in cell})[-days:]
        out = []
        for day in days_sorted:
            for shift in ("A", "B", "C"):
                c = cell.get((day, shift))
                if not c:
                    continue
                out.append({"date": day, "shift": shift, "planned_min": round(c["planned"] / 60, 1),
                            "downtime_min": round((c["planned"] - c["run"]) / 60, 1),
                            "stopped_min": round(c["stopped"] / 60, 1),
                            "idle_min": round((c["planned"] - c["run"] - c["stopped"]) / 60, 1),
                            "by_machine": {k: round(v / 60, 1) for k, v in sorted(c["by"].items())}})
        by_shift = {sh: round(sum(r["downtime_min"] for r in out if r["shift"] == sh), 1) for sh in ("A", "B", "C")}
        return {"days": days, "rows": out, "total_by_shift": by_shift,
                "shifts": {"A": "06:00-14:00", "B": "14:00-22:00", "C": "22:00-06:00"}, "timezone": time.strftime("%Z")}

    def report_ml_accuracy(self) -> dict:
        ml = [a for a in self.alerts.alerts.values() if a.level == "yellow"]
        fb = [a for a in ml if a.feedback]
        tp = sum(1 for a in fb if a.feedback["verdict"] == "true_positive")
        fp = sum(1 for a in fb if a.feedback["verdict"] == "false_positive")
        all_fb = [a for a in self.alerts.alerts.values() if a.feedback]
        return {
            "yellow_alerts": len(ml), "with_feedback": len(fb), "true_positive": tp, "false_positive": fp,
            "precision": round(tp / (tp + fp), 4) if tp + fp else None,
            "feedback_coverage": round(len(fb) / len(ml), 3) if ml else None,
            "all_levels_feedback": {"true_positive": sum(1 for a in all_fb if a.feedback["verdict"] == "true_positive"),
                                    "false_positive": sum(1 for a in all_fb if a.feedback["verdict"] == "false_positive")},
            "offline_validation": self.scorer.meta.get("validation"),
            "model": {k: self.scorer.meta.get(k) for k in ("trained_at", "algorithm", "training_rows", "training_data")},
        }

    # ------------------------------------------------------------------ metrics
    def metrics(self) -> dict:
        def pct(vals, q):
            if not vals:
                return None
            v = sorted(vals)
            return round(v[min(len(v) - 1, int(q * len(v)))], 2)

        lat, inf, tk = list(self.latency_ms), list(self.infer_ms), list(self.tick_ms)
        return {
            "uptime_s": round(time.time() - self.started, 1),
            "targets": {"update_latency_ms": 1000, "inference_ms": 200, "mqtt_reconnect_s": 5, "ws_clients": 50},
            "latency_ms": {"p50": pct(lat, 0.5), "p95": pct(lat, 0.95), "max": round(max(lat), 2) if lat else None,
                           "samples": len(lat), "definition": "sample emission -> engine broadcast"},
            "inference_ms": {"last": round(self.scorer.last_ms, 2), "p50": pct(inf, 0.5), "p95": pct(inf, 0.95),
                             "max": round(max(inf), 2) if inf else None},
            "tick_ms": {"p50": pct(tk, 0.5), "p95": pct(tk, 0.95), "max": round(max(tk), 2) if tk else None},
            "ingest": dict(self.stats),
            "ml": {"ready": self.scorer.ready, "outage": self.scorer.outage, "model": self.scorer.meta.get("trained_at")},
            "mqtt": self.mqtt_status,
            "simulator": self.sim_status,
            "backfill": self.backfill_info,
            "storage": self.repo.health(),
            "retention": {"raw_telemetry": "30 days (InfluxDB bucket telemetry_raw)",
                          "aggregated": "1 year (InfluxDB bucket telemetry_agg)"},
        }
