"""Alert lifecycle: open -> acknowledged -> resolved, plus auto-clear when the condition disappears.

Level priority per machine: red (rule) > orange (projected fault) > yellow (ML caution) > green.
Lower-level alerts are suppressed while a higher one is active so the feed stays readable.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from .rules import Condition

LEVEL_RANK = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
OPEN_AFTER = {"red": 1, "orange": 2, "yellow": 2}       # consecutive ticks a condition must hold
CLEAR_AFTER_S = {"red": 3.0, "orange": 4.0, "yellow": 4.0}


@dataclass
class Alert:
    id: int
    machine_id: str
    level: str
    kind: str
    title: str
    message: str
    opened_at: float
    value: float | None = None
    threshold: float | None = None
    eta_s: float | None = None
    score: float | None = None
    peak: float | None = None
    status: str = "open"            # open | acknowledged | cleared | resolved
    active: bool = True
    last_seen: float = 0.0
    cleared_at: float | None = None
    clear_reason: str | None = None
    acked_by: str | None = None
    acked_at: float | None = None
    technician: str | None = None
    resolved_by: str | None = None
    resolved_at: float | None = None
    resolution_notes: str | None = None
    feedback: dict | None = None

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["duration_s"] = round((self.cleared_at or time.time()) - self.opened_at, 1)
        return d


@dataclass
class _Track:
    streak: int = 0
    absent_since: float | None = None
    alert_id: int | None = None
    cond: Condition | None = None


class AlertManager:
    def __init__(self, on_event: Callable[[str, Alert], None] | None = None):
        self.alerts: dict[int, Alert] = {}
        self._tracks: dict[tuple[str, str], _Track] = {}
        self._next_id = 1
        self.on_event = on_event or (lambda e, a: None)

    # ------------------------------------------------------------------ loading
    def load(self, rows: list[dict]) -> None:
        fields = Alert.__dataclass_fields__
        for r in rows:
            a = Alert(**{k: v for k, v in r.items() if k in fields})
            if a.active:                       # anything live at shutdown is history now
                a.active, a.status, a.cleared_at = False, ("resolved" if a.status == "resolved" else "cleared"), a.cleared_at or time.time()
                a.clear_reason = a.clear_reason or "service restart"
            self.alerts[a.id] = a
            self._next_id = max(self._next_id, a.id + 1)

    # ------------------------------------------------------------------ evaluation
    def update(self, machine_id: str, conditions: list[Condition], now: float) -> str:
        """Feed the current conditions for one machine; returns its resulting level."""
        top = max((LEVEL_RANK[c.level] for c in conditions), default=0)
        wanted = {c.kind: c for c in conditions if LEVEL_RANK[c.level] == top}

        # level of the highest alert that is actually open right now (a lower alert is only
        # superseded once the higher one has opened - no flash of green while escalating)
        open_rank = max((LEVEL_RANK[self.alerts[t.alert_id].level] for (m, _k), t in self._tracks.items()
                         if m == machine_id and t.alert_id is not None), default=0)
        # tracks for this machine
        kinds = {k for (m, k) in self._tracks if m == machine_id} | set(wanted)
        for kind in kinds:
            tr = self._tracks.setdefault((machine_id, kind), _Track())
            cond = wanted.get(kind)
            if cond is not None:
                tr.streak += 1
                tr.absent_since = None
                tr.cond = cond
                if tr.alert_id is None and tr.streak >= OPEN_AFTER[cond.level]:
                    tr.alert_id = self._open(machine_id, cond, now).id
                elif tr.alert_id is not None:
                    self._refresh(self.alerts[tr.alert_id], cond, now)
            else:
                tr.streak = 0
                if tr.alert_id is not None:
                    # a higher level alert took over -> close right away, otherwise debounce
                    superseded = tr.cond is not None and open_rank > LEVEL_RANK[tr.cond.level]
                    if tr.absent_since is None:
                        tr.absent_since = now
                    level = tr.cond.level if tr.cond else "red"
                    if superseded or now - tr.absent_since >= CLEAR_AFTER_S[level]:
                        self._clear(self.alerts[tr.alert_id], now, "superseded by higher level" if superseded else "condition cleared")
                        tr.alert_id = None
                        tr.absent_since = None
                else:
                    tr.absent_since = None
        # machine level = highest active alert (debounced)
        level = "green"
        for (m, _k), tr in self._tracks.items():
            if m == machine_id and tr.alert_id is not None:
                lv = self.alerts[tr.alert_id].level
                if LEVEL_RANK[lv] > LEVEL_RANK[level]:
                    level = lv
        return level

    def _open(self, machine_id: str, c: Condition, now: float) -> Alert:
        a = Alert(id=self._next_id, machine_id=machine_id, level=c.level, kind=c.kind, title=c.title,
                  message=c.message, opened_at=now, value=c.value, threshold=c.threshold, last_seen=now,
                  peak=c.value)
        self._next_id += 1
        self.alerts[a.id] = a
        self.on_event("opened", a)
        return a

    def _refresh(self, a: Alert, c: Condition, now: float) -> None:
        a.last_seen = now
        a.value = c.value
        a.message = c.message
        if c.value is not None:
            a.peak = c.value if a.peak is None else max(a.peak, c.value)

    def _clear(self, a: Alert, now: float, reason: str) -> None:
        a.active = False
        a.cleared_at = now
        a.clear_reason = reason
        if a.status in ("open", "acknowledged"):
            a.status = "resolved" if a.status == "acknowledged" else "cleared"
            if a.status == "resolved":
                a.resolved_at, a.resolved_by = now, a.acked_by
                a.resolution_notes = a.resolution_notes or "Condition cleared after acknowledgement"
        self.on_event("cleared", a)

    def attach_extra(self, alert_id: int, **fields) -> None:
        a = self.alerts.get(alert_id)
        if a:
            for k, v in fields.items():
                setattr(a, k, v)

    # ------------------------------------------------------------------ operator actions
    def get(self, alert_id: int) -> Alert | None:
        return self.alerts.get(alert_id)

    def acknowledge(self, alert_id: int, user: str) -> Alert:
        a = self._need(alert_id)
        if a.status == "open":
            a.status, a.acked_by, a.acked_at = "acknowledged", user, time.time()
            self.on_event("acknowledged", a)
        return a

    def assign(self, alert_id: int, technician: str, user: str) -> Alert:
        a = self._need(alert_id)
        a.technician = technician
        if a.status == "open":
            a.status, a.acked_by, a.acked_at = "acknowledged", user, time.time()
        self.on_event("assigned", a)
        return a

    def resolve(self, alert_id: int, user: str, notes: str) -> Alert:
        a = self._need(alert_id)
        a.status, a.resolved_by, a.resolved_at, a.resolution_notes = "resolved", user, time.time(), notes
        if a.acked_by is None:
            a.acked_by, a.acked_at = user, a.resolved_at
        self.on_event("resolved", a)
        return a

    def feedback(self, alert_id: int, user: str, verdict: str, comment: str) -> Alert:
        a = self._need(alert_id)
        a.feedback = {"verdict": verdict, "by": user, "at": time.time(), "comment": comment}
        self.on_event("feedback", a)
        return a

    def _need(self, alert_id: int) -> Alert:
        a = self.alerts.get(alert_id)
        if a is None:
            raise KeyError(alert_id)
        return a

    # ------------------------------------------------------------------ queries
    def list(self, *, level: str | None = None, status: str | None = None, machine_id: str | None = None,
             active: bool | None = None, limit: int = 200) -> list[Alert]:
        out = []
        for a in sorted(self.alerts.values(), key=lambda x: x.id, reverse=True):
            if level and a.level != level:
                continue
            if status and a.status != status:
                continue
            if machine_id and a.machine_id != machine_id:
                continue
            if active is not None and a.active != active:
                continue
            out.append(a)
            if len(out) >= limit:
                break
        return out

    def active_count(self) -> int:
        return sum(1 for a in self.alerts.values() if a.active)

    def trim(self, keep: int = 5000) -> None:
        if len(self.alerts) > keep:
            for aid in sorted(self.alerts)[: len(self.alerts) - keep]:
                if not self.alerts[aid].active:
                    del self.alerts[aid]


__all__ = ["Alert", "AlertManager", "LEVEL_RANK"]
