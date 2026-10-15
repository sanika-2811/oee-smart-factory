"""Virtual factory: pure-Python (stdlib only) signal model for the simulated machines.

``Factory.step(dt, ts)`` advances a *virtual* clock and returns one telemetry dict per
machine. The same code drives (a) the live MQTT simulator, (b) the in-process
``direct`` mode, (c) the history back-fill used for the reports and (d) the synthetic
training data for the Isolation Forest.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Any

from .profiles import MachineProfile

AMBIENT_C = 31.0
FAULT_KINDS = ("temp_ramp", "vib_spike", "stop", "anomaly")


@dataclass
class Fault:
    kind: str
    start: float
    duration: float
    params: dict[str, float] = field(default_factory=dict)

    def elapsed(self, ts: float) -> float:
        return ts - self.start

    def active(self, ts: float) -> bool:
        return self.start <= ts < self.start + self.duration


class MachineSim:
    def __init__(self, profile: MachineProfile, rng: random.Random, start_ts: float, random_events: bool = False):
        self.p = profile
        self.rng = rng
        self.random_events = random_events
        self.status = "RUNNING"
        self.status_until = 0.0
        self.temp = profile.base_temp
        self.vib = profile.base_vib
        self.speed = profile.perf_mean
        self.drift_walk = 0.0
        self.phase = rng.uniform(0, 2 * math.pi)
        self.cycle_acc = rng.random()
        self.cycles = rng.randint(1_000, 5_000)
        self.good = self.cycles
        self.faults: dict[str, Fault] = {}
        self.temp_fault = 0.0       # additive deg C produced by faults
        self.vib_fault = 0.0        # additive mm/s produced by faults
        self.noise_fault = 0.0      # extra vibration noise multiplier produced by faults
        self.last_ts = start_ts
        self.last_fault_end = -1e9

    # ----------------------------------------------------------------- fault control
    def inject(self, kind: str, ts: float, duration: float | None = None) -> Fault:
        p = self.p
        if kind == "temp_ramp":
            duration = duration or 180.0
            nominal = p.base_temp + p.temp_drift * 0.2
            rise = (p.temp_limit + 6.0) - nominal
            f = Fault(kind, ts, duration, {"rise": rise, "hold": 12.0})
            f.duration = duration + 12.0   # ramp + short hold above the limit
            f.params["ramp"] = duration
        elif kind == "vib_spike":
            duration = duration or 20.0
            f = Fault(kind, ts, duration, {"target": p.vib_limit * 1.35})
        elif kind == "stop":
            duration = duration or 45.0
            f = Fault(kind, ts, duration)
        elif kind == "anomaly":
            duration = duration or 45.0
            # bearing-wear signature: warmer, more vibration and a much noisier vibration signal -
            # all below the hard limits, so only the ML model notices
            f = Fault(kind, ts, duration, {"dtemp": 3.3 * p.temp_scale, "dvib": 3.3 * p.vib_scale, "noise": 3.0})
        else:
            raise ValueError(f"unknown fault kind {kind!r}")
        self.faults[kind] = f
        return f

    def clear(self) -> None:
        self.faults.clear()

    def active_faults(self, ts: float) -> list[str]:
        return [k for k, f in self.faults.items() if f.active(ts)]

    # ----------------------------------------------------------------- stepping
    def _target_temp(self, ts: float) -> float:
        p = self.p
        if self.status == "STOPPED":
            return AMBIENT_C
        daily = p.temp_drift * math.sin(2 * math.pi * (ts % 86400.0) / 86400.0 + self.phase)
        t = p.base_temp + daily + self.drift_walk
        return t - 7.0 if self.status == "IDLE" else t

    def step(self, dt: float, ts: float) -> dict[str, Any]:
        p, rng = self.p, self.rng
        # ---- slow random walk of the operating point (mean-reverting)
        self.drift_walk += (-self.drift_walk * dt / 900.0) + rng.gauss(0, 0.04) * math.sqrt(dt)
        self.drift_walk = max(-1.5, min(1.5, self.drift_walk))

        # ---- faults -> forced status / additive offsets
        forced_stop = False
        temp_target_fault = 0.0
        vib_target_fault = 0.0
        noise_target = 0.0
        for kind, f in list(self.faults.items()):
            if ts >= f.start + f.duration:
                if kind == "stop":
                    self.status, self.status_until = "RUNNING", 0.0
                del self.faults[kind]
                continue
            e = f.elapsed(ts)
            if kind == "temp_ramp":
                temp_target_fault = max(temp_target_fault, f.params["rise"] * min(e / f.params["ramp"], 1.0))
            elif kind == "vib_spike":
                vib_target_fault = max(vib_target_fault, (f.params["target"] - p.base_vib) * min(e / 2.0, 1.0))
            elif kind == "anomaly":
                k = min(e / 4.0, 1.0)
                temp_target_fault = max(temp_target_fault, f.params["dtemp"] * k)
                vib_target_fault = max(vib_target_fault, f.params["dvib"] * k)
                noise_target = max(noise_target, f.params["noise"] * k)
            elif kind == "stop":
                forced_stop = True
        # faults follow their profile while active, otherwise decay (cool down)
        if temp_target_fault > 0:
            self.temp_fault = temp_target_fault
        else:
            self.temp_fault *= math.exp(-dt / 25.0)
        if vib_target_fault > 0:
            self.vib_fault = vib_target_fault
        else:
            self.vib_fault *= math.exp(-dt / 4.0)
        self.noise_fault = noise_target if noise_target > 0 else self.noise_fault * math.exp(-dt / 4.0)

        # ---- status machine (micro-stops, optional unplanned stops, forced stops)
        if forced_stop:
            self.status = "STOPPED"
        elif self.status in ("IDLE", "STOPPED") and ts >= self.status_until:
            self.status = "RUNNING"
        elif self.status == "RUNNING":
            if rng.random() < p.microstop_per_hour * dt / 3600.0:
                self.status, self.status_until = "IDLE", ts + rng.uniform(3.0, 11.0)
            elif self.random_events and rng.random() < dt / (36 * 3600.0):
                self.status, self.status_until = "STOPPED", ts + rng.uniform(180.0, 720.0)

        # ---- thermal + vibration dynamics
        tau = {"RUNNING": 25.0, "IDLE": 40.0, "STOPPED": 160.0}[self.status]
        self.temp += (self._target_temp(ts) - self.temp) * (1.0 - math.exp(-dt / tau))
        if self.status == "RUNNING":
            vib_nominal = p.base_vib * (1.0 + 0.05 * (self.temp - p.base_temp) / max(p.temp_scale, 0.1))
            vib = vib_nominal + rng.gauss(0, p.vib_noise * (1.0 + self.noise_fault))
        elif self.status == "IDLE":
            vib = 0.22 * p.base_vib + rng.gauss(0, p.vib_noise * 0.3)
        else:
            vib = 0.03 + abs(rng.gauss(0, 0.01))
        temp_out = self.temp + rng.gauss(0, p.temp_noise)
        if self.status != "STOPPED":
            temp_out += self.temp_fault
            vib += self.vib_fault
        elif self.faults.get("temp_ramp"):
            temp_out += self.temp_fault
        temp_out = max(temp_out, 0.5)
        vib = max(vib, 0.0)

        # ---- production
        if self.status == "RUNNING":
            self.speed += (p.perf_mean - self.speed) * min(dt / 120.0, 1.0) + rng.gauss(0, 0.02) * math.sqrt(min(dt, 5.0))
            self.speed = max(0.55, min(1.04, self.speed))
            self.cycle_acc += dt * self.speed / p.ideal_cycle_s
            n = int(self.cycle_acc)
            if n:
                self.cycle_acc -= n
                self.cycles += n
                self.good += sum(1 for _ in range(n) if rng.random() >= p.reject_rate)
        self.last_ts = ts
        return {
            "machine_id": p.id,
            "ts": ts,
            "temperature": round(temp_out, 2),
            "vibration": round(vib, 3),
            "status": self.status,
            "cycle_count": self.cycles,
            "good_count": self.good,
        }


class Factory:
    def __init__(self, profiles: list[MachineProfile], seed: int | None = None, start_ts: float | None = None,
                 random_events: bool = False):
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        start = start_ts if start_ts is not None else time.time()
        self.profiles = {p.id: p for p in profiles}
        self.machines = {
            p.id: MachineSim(p, random.Random(f"{self.seed}:{p.id}"), start, random_events) for p in profiles
        }
        self.time_scale = 1.0   # >1 compresses injected fault durations (demo speed)

    def step(self, dt: float, ts: float) -> list[dict[str, Any]]:
        return [m.step(dt, ts) for m in self.machines.values()]

    def inject(self, machine_id: str, kind: str, ts: float, duration: float | None = None) -> dict[str, Any]:
        if machine_id not in self.machines:
            raise KeyError(machine_id)
        if duration is not None:
            duration = duration / self.time_scale
        elif kind == "temp_ramp":
            duration = 180.0 / self.time_scale
        f = self.machines[machine_id].inject(kind, ts, duration)
        return {"machine_id": machine_id, "kind": kind, "start": f.start, "duration": f.duration}

    def clear(self, machine_id: str | None = None) -> None:
        for mid, m in self.machines.items():
            if machine_id in (None, mid):
                m.clear()
                if m.status == "STOPPED" and m.status_until <= m.last_ts:
                    m.status = "RUNNING"

    def active_faults(self, ts: float) -> dict[str, list[str]]:
        return {mid: m.active_faults(ts) for mid, m in self.machines.items() if m.faults}
