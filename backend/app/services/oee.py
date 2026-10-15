"""OEE = Availability x Performance x Quality over rolling 1 h / 8 h windows (FR-02).

Samples are folded into 5-second buckets so a window is an O(1) running sum no matter how
many machines or how fast data arrives.

    Availability = run time / observed (planned) time
    Performance  = (cycles x ideal cycle time) / run time          (capped at 100 %)
    Quality      = good cycles / total cycles
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

BUCKET_S = 5
MAX_GAP_S = 30.0           # a gap longer than this is "no data", not downtime
PLANNED, RUN, IDEAL, CYCLES, GOOD, STOPPED_T = range(6)
WINDOWS = {"1h": 3600, "8h": 8 * 3600}


class RollingTotals:
    def __init__(self, window_s: int):
        self.n_buckets = window_s // BUCKET_S
        self.buckets: deque[tuple[int, list[float]]] = deque()
        self.totals = [0.0] * 6

    def add(self, ts: float, vals: list[float]) -> None:
        idx = int(ts // BUCKET_S)
        if self.buckets and idx <= self.buckets[-1][0]:
            bucket = self.buckets[-1][1]
        else:
            bucket = [0.0] * 6
            self.buckets.append((idx, bucket))
        for i, v in enumerate(vals):
            bucket[i] += v
            self.totals[i] += v
        horizon = self.buckets[-1][0] - self.n_buckets
        while self.buckets and self.buckets[0][0] <= horizon:
            _, old = self.buckets.popleft()
            for i, v in enumerate(old):
                self.totals[i] -= v

    def snapshot(self) -> list[float]:
        return [max(v, 0.0) for v in self.totals]


def compute_oee(totals: list[float]) -> dict[str, float]:
    planned, run, ideal, cycles, good = totals[PLANNED], totals[RUN], totals[IDEAL], totals[CYCLES], totals[GOOD]
    availability = run / planned if planned > 0 else 0.0
    performance = min(ideal / run, 1.0) if run > 0 else 0.0
    quality = min(good / cycles, 1.0) if cycles > 0 else (1.0 if run > 0 else 0.0)
    return {
        "availability": round(availability * 100, 2),
        "performance": round(performance * 100, 2),
        "quality": round(quality * 100, 2),
        "oee": round(availability * performance * quality * 100, 2),
        "planned_s": round(planned, 1),
        "run_s": round(run, 1),
        "cycles": int(round(cycles)),
        "good": int(round(good)),
    }


@dataclass
class _Prev:
    ts: float
    cycles: int
    good: int


class MachineOEE:
    """Per-machine accumulator. ``hourly`` feeds the historical reports (7-day trend, shift downtime)."""

    def __init__(self, ideal_cycle_s: float):
        self.ideal_cycle_s = ideal_cycle_s
        self.windows = {name: RollingTotals(sec) for name, sec in WINDOWS.items()}
        self.hourly: dict[int, list[float]] = {}
        self.dirty_hours: set[int] = set()
        self.prev: _Prev | None = None

    def reset_baseline(self) -> None:
        """Forget the previous sample (e.g. simulator restarted / back-fill finished)."""
        self.prev = None

    def update(self, ts: float, status: str, cycle_count: int, good_count: int | None) -> None:
        prev, good_count = self.prev, (cycle_count if good_count is None else good_count)
        self.prev = _Prev(ts, cycle_count, good_count)
        if prev is None:
            return
        dt = ts - prev.ts
        if dt <= 0 or dt > MAX_GAP_S:
            return
        dcyc = cycle_count - prev.cycles
        dgood = good_count - prev.good
        if dcyc < 0 or dgood < 0:       # counter reset
            dcyc = dgood = 0
        dgood = min(dgood, dcyc)
        run = dt if status == "RUNNING" else 0.0
        vals = [dt, run, dcyc * self.ideal_cycle_s, float(dcyc), float(dgood), dt if status == "STOPPED" else 0.0]
        for w in self.windows.values():
            w.add(ts, vals)
        hour = int(ts // 3600) * 3600
        row = self.hourly.setdefault(hour, [0.0] * 6)
        for i, v in enumerate(vals):
            row[i] += v
        self.dirty_hours.add(hour)

    def result(self) -> dict[str, dict[str, float]]:
        return {name: compute_oee(w.snapshot()) for name, w in self.windows.items()}


def plant_oee(machines: list[MachineOEE]) -> dict[str, dict[str, float]]:
    out = {}
    for name in WINDOWS:
        total = [0.0] * 6
        for m in machines:
            for i, v in enumerate(m.windows[name].snapshot()):
                total[i] += v
        out[name] = compute_oee(total)
    return out
