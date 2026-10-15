"""Deterministic IF-THEN-ELSE rule engine for hard (Red) faults (FR-03)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Condition:
    kind: str                    # temp_high | vib_high | machine_down | projected_fault | ml_anomaly
    level: str                   # red | orange | yellow
    title: str
    message: str
    value: float | None = None
    threshold: float | None = None


def evaluate_rules(temp_limit: float, vib_limit: float, temperature: float, vibration: float, status: str,
                   machine_name: str = "") -> list[Condition]:
    out: list[Condition] = []
    if temperature > temp_limit:
        out.append(Condition("temp_high", "red", "Temperature over limit",
                             f"{temperature:.1f} °C exceeds the {temp_limit:.0f} °C hard limit",
                             temperature, temp_limit))
    if vibration > vib_limit:
        out.append(Condition("vib_high", "red", "Vibration over limit",
                             f"{vibration:.2f} mm/s exceeds the {vib_limit:.1f} mm/s hard limit",
                             vibration, vib_limit))
    if status == "STOPPED":
        out.append(Condition("machine_down", "red", "Machine down", "Machine reports STOPPED", None, None))
    return out
