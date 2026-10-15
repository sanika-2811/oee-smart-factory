"""Feature engineering shared by training (vectorised) and live inference (streaming).

Features are normalised per machine so ONE Isolation Forest serves every machine:
    z_level = sqrt(z_temp^2 + z_vib^2)             (joint level deviation)
    z_dyn   = sqrt(z_dtemp^2 + max(z_vstd-0.4,0)^2) (joint dynamic deviation)
    z_temp  = (temperature - base_temp) / temp_scale
    z_vib   = (vibration   - base_vib ) / vib_scale
    z_dtemp = (temperature change over the last 10 s) / temp_scale
    z_vstd  = (std-dev of vibration over the last 10 s) / vib_scale
"""
from __future__ import annotations

import math
from collections import deque

import numpy as np

FEATURE_NAMES = ["z_temp", "z_vib", "z_dtemp", "z_vstd", "z_level", "z_dyn"]
WINDOW_S = 10.0


def augment(x: np.ndarray) -> np.ndarray:
    """Append the two joint-magnitude features (makes single-axis level shifts easier to isolate)."""
    x = np.atleast_2d(np.asarray(x, dtype=float))
    level = np.sqrt(x[:, 0] ** 2 + x[:, 1] ** 2)
    dyn = np.sqrt(x[:, 2] ** 2 + np.maximum(x[:, 3] - 0.4, 0.0) ** 2)
    return np.column_stack([x, level, dyn])


class StreamFeatures:
    """Rolling 10-second window for one machine."""

    def __init__(self, base_temp: float, base_vib: float, temp_scale: float, vib_scale: float, vib_noise: float):
        self.base_temp, self.base_vib = base_temp, base_vib
        self.temp_scale, self.vib_scale, self.vib_noise = temp_scale, vib_scale, vib_noise
        self.win: deque[tuple[float, float, float, bool]] = deque()

    def push(self, ts: float, temp: float, vib: float, running: bool = True) -> None:
        self.win.append((ts, temp, vib, running))
        while self.win and ts - self.win[0][0] > WINDOW_S:
            self.win.popleft()

    @property
    def clean(self) -> bool:
        """True when the whole 10 s window is RUNNING data (status transitions are not scored)."""
        w = self.win
        return len(w) >= 4 and (w[-1][0] - w[0][0]) >= WINDOW_S * 0.8 and all(x[3] for x in w)

    def vector(self, temp: float, vib: float) -> list[float]:
        w = self.win
        dtemp = (w[-1][1] - w[0][1]) if len(w) >= 4 else 0.0
        if len(w) >= 4:
            mean = sum(x[2] for x in w) / len(w)
            vstd = math.sqrt(sum((x[2] - mean) ** 2 for x in w) / len(w))
        else:
            vstd = self.vib_noise
        zt, zv = (temp - self.base_temp) / self.temp_scale, (vib - self.base_vib) / self.vib_scale
        zd, zs = dtemp / self.temp_scale, vstd / self.vib_scale
        return [zt, zv, zd, zs, math.hypot(zt, zv), math.hypot(zd, max(zs - 0.4, 0.0))]


def batch_features(temps: np.ndarray, vibs: np.ndarray, running: np.ndarray, profile, step_s: float):
    """Vectorised equivalent of ``StreamFeatures``. Returns (features, clean_mask)."""
    n = len(temps)
    w = max(int(round(WINDOW_S / step_s)), 2)
    z_temp = (temps - profile.base_temp) / profile.temp_scale
    z_vib = (vibs - profile.base_vib) / profile.vib_scale
    dtemp = np.zeros(n)
    dtemp[w:] = temps[w:] - temps[:-w]
    csum = np.concatenate([[0.0], np.cumsum(vibs)])
    csq = np.concatenate([[0.0], np.cumsum(vibs ** 2)])
    idx = np.arange(n)
    lo = np.maximum(idx - w, 0)
    cnt = (idx - lo + 1).astype(float)
    # window is samples (lo..idx] inclusive of idx  -> use prefix sums
    s1 = csum[idx + 1] - csum[lo]
    s2 = csq[idx + 1] - csq[lo]
    var = np.maximum(s2 / cnt - (s1 / cnt) ** 2, 0.0)
    vstd = np.sqrt(var)
    vstd[: 4] = profile.vib_noise
    bad = np.concatenate([[0], np.cumsum(~running)])
    clean = (bad[idx + 1] - bad[lo] == 0) & (idx >= int(WINDOW_S * 0.8 / step_s))
    X = augment(np.column_stack([z_temp, z_vib, dtemp / profile.temp_scale, vstd / profile.vib_scale]))
    return X, clean
