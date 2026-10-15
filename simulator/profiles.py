"""Machine catalogue shared by the simulator, the backend and the ML trainer.

The first five entries are the machines named in the SRS. ``build_profiles(n)``
returns the first ``n`` of a 20-entry catalogue, which is how the system scales
from 5 to 20 machines (FR-11 / NFR-SC1). A JSON file can override the catalogue
(see ``MACHINES_FILE``) so every number below stays configurable.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Any

STATUSES = ("RUNNING", "IDLE", "STOPPED")


@dataclass(frozen=True)
class MachineProfile:
    id: str
    name: str
    kind: str
    # --- normal operating behaviour -------------------------------------------------
    base_temp: float          # deg C while running at nominal load
    temp_noise: float         # std-dev of measurement noise (deg C)
    temp_drift: float         # amplitude of the slow "daily" drift (deg C)
    base_vib: float           # mm/s RMS while running
    vib_noise: float
    # --- production -----------------------------------------------------------------
    ideal_cycle_s: float      # ideal (rated) cycle time in seconds
    perf_mean: float          # average speed as a fraction of rated speed
    reject_rate: float        # fraction of cycles that are scrap
    microstop_per_hour: float  # average number of short idle micro-stops per hour
    # --- hard thresholds (rule engine) ----------------------------------------------
    temp_limit: float = 85.0
    vib_limit: float = 7.0
    # --- scale used to normalise ML features ---------------------------------------
    temp_scale: float = 3.0   # typical spread of normal temperature around base_temp
    vib_scale: float = 0.35

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_CATALOGUE: list[dict[str, Any]] = [
    dict(id="CNC-01", name="CNC Mill", kind="Machining", base_temp=62.0, temp_noise=0.35, temp_drift=2.5,
         base_vib=2.4, vib_noise=0.12, ideal_cycle_s=12, perf_mean=0.92, reject_rate=0.020, microstop_per_hour=9,
         temp_limit=85, vib_limit=7.0),
    dict(id="Press-02", name="Hydraulic Press", kind="Forming", base_temp=58.0, temp_noise=0.40, temp_drift=3.0,
         base_vib=3.1, vib_noise=0.16, ideal_cycle_s=6, perf_mean=0.88, reject_rate=0.035, microstop_per_hour=12,
         temp_limit=85, vib_limit=8.0),
    dict(id="Conveyor-03", name="Main Conveyor", kind="Transport", base_temp=44.0, temp_noise=0.25, temp_drift=1.8,
         base_vib=1.6, vib_noise=0.08, ideal_cycle_s=2, perf_mean=0.96, reject_rate=0.008, microstop_per_hour=5,
         temp_limit=80, vib_limit=5.0, temp_scale=2.4, vib_scale=0.25),
    dict(id="Welder-04", name="Robotic Welder", kind="Joining", base_temp=68.0, temp_noise=0.50, temp_drift=3.2,
         base_vib=2.0, vib_noise=0.10, ideal_cycle_s=9, perf_mean=0.85, reject_rate=0.050, microstop_per_hour=14,
         temp_limit=90, vib_limit=6.0, temp_scale=3.4),
    dict(id="Packer-05", name="Packaging Unit", kind="Packaging", base_temp=47.0, temp_noise=0.28, temp_drift=2.0,
         base_vib=1.9, vib_noise=0.09, ideal_cycle_s=4, perf_mean=0.94, reject_rate=0.012, microstop_per_hour=7,
         temp_limit=80, vib_limit=5.5, temp_scale=2.4, vib_scale=0.28),
]

_EXTRA_KINDS = [
    ("Lathe", "Machining", 60, 2.3, 10, 0.90, 0.025),
    ("Drill", "Machining", 55, 2.0, 8, 0.93, 0.018),
    ("Grinder", "Finishing", 64, 2.8, 7, 0.89, 0.030),
    ("Mixer", "Processing", 52, 1.7, 15, 0.95, 0.010),
    ("Cutter", "Machining", 61, 2.6, 5, 0.91, 0.022),
    ("Stamper", "Forming", 57, 3.0, 6, 0.87, 0.040),
    ("Painter", "Coating", 49, 1.4, 11, 0.94, 0.020),
    ("Oven", "Thermal", 72, 1.2, 30, 0.97, 0.006),
    ("Sorter", "Transport", 43, 1.5, 3, 0.96, 0.010),
    ("Labeler", "Packaging", 46, 1.6, 4, 0.95, 0.008),
    ("Palletizer", "Packaging", 48, 2.1, 12, 0.90, 0.012),
    ("Inspector", "Quality", 42, 1.1, 3, 0.97, 0.004),
    ("Extruder", "Forming", 70, 2.7, 14, 0.88, 0.028),
    ("Polisher", "Finishing", 56, 2.2, 6, 0.92, 0.016),
    ("Router", "Machining", 59, 2.5, 9, 0.91, 0.021),
]


def _extra_profiles() -> list[dict[str, Any]]:
    out = []
    for i, (name, kind, temp, vib, cycle, perf, rej) in enumerate(_EXTRA_KINDS, start=6):
        out.append(dict(
            id=f"{name}-{i:02d}", name=name, kind=kind, base_temp=float(temp), temp_noise=0.35, temp_drift=2.4,
            base_vib=float(vib), vib_noise=0.11, ideal_cycle_s=float(cycle), perf_mean=perf, reject_rate=rej,
            microstop_per_hour=8 + (i % 5), temp_limit=85.0 if temp < 66 else 92.0, vib_limit=round(vib * 2.9, 1),
            temp_scale=3.0, vib_scale=round(max(vib * 0.14, 0.15), 2),
        ))
    return out


def catalogue() -> list[MachineProfile]:
    path = os.environ.get("MACHINES_FILE", "").strip()
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return [MachineProfile(**row) for row in json.load(fh)]
    return [MachineProfile(**row) for row in _CATALOGUE + _extra_profiles()]


def build_profiles(count: int | None = None) -> list[MachineProfile]:
    """Return the first ``count`` machines (default: ``MACHINE_COUNT`` env, else 5)."""
    cat = catalogue()
    if count is None:
        count = int(os.environ.get("MACHINE_COUNT", "5"))
    count = max(1, min(count, len(cat)))
    return cat[:count]


__all__ = ["MachineProfile", "build_profiles", "catalogue", "STATUSES"]
