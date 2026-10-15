"""What-If degradation projection (FR-07): least-squares line ``y = m*x + c`` through the last
3 minutes of temperature and the time at which that line crosses the hard threshold."""
from __future__ import annotations

from typing import Sequence


def fit_line(points: Sequence[tuple[float, float]]) -> tuple[float, float, float] | None:
    """Return (m, c, r2) for y = m*x + c via ordinary least squares, or None if degenerate."""
    n = len(points)
    if n < 2:
        return None
    sx = sum(p[0] for p in points)
    sy = sum(p[1] for p in points)
    sxx = sum(p[0] * p[0] for p in points)
    sxy = sum(p[0] * p[1] for p in points)
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-12:
        return None
    m = (n * sxy - sx * sy) / denom
    c = (sy - m * sx) / n
    mean_y = sy / n
    ss_tot = sum((p[1] - mean_y) ** 2 for p in points)
    ss_res = sum((p[1] - (m * p[0] + c)) ** 2 for p in points)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0
    return m, c, max(0.0, min(1.0, r2))


def project(points: Sequence[tuple[float, float]], now: float, limit: float, *, horizon_s: float = 60.0,
            min_slope: float = 0.03, min_r2: float = 0.6, min_points: int = 30) -> dict:
    """Analyse (timestamp, temperature) points. x is seconds since the first point of the window."""
    base = {"ready": False, "projected": False, "n": len(points), "limit": limit, "horizon_s": horizon_s,
            "slope_c_per_s": 0.0, "slope_c_per_min": 0.0, "intercept": 0.0, "r2": 0.0, "eta_s": None,
            "fit_now": None, "t0": points[0][0] if points else now}
    if len(points) < min_points:
        return base
    t0 = points[0][0]
    pts = [(t - t0, y) for t, y in points]
    fit = fit_line(pts)
    if fit is None:
        return base
    m, c, r2 = fit
    x_now = now - t0
    fit_now = m * x_now + c
    eta = None
    if m > 1e-9 and fit_now < limit:
        eta = (limit - fit_now) / m
    projected = bool(eta is not None and m >= min_slope and r2 >= min_r2 and 0 < eta <= horizon_s)
    base.update(ready=True, projected=projected, slope_c_per_s=round(m, 5), slope_c_per_min=round(m * 60, 3),
                intercept=round(c, 3), r2=round(r2, 4), eta_s=None if eta is None else round(eta, 1),
                fit_now=round(fit_now, 2))
    return base
