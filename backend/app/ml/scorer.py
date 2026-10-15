"""Isolation Forest inference service (FR-04): raw score -> Anomaly Score 0-100 %.

The model is trained offline once (``python -m app.ml.train``; auto-run on first start) and
loaded from ``model.pkl``. Inference for a whole tick (all machines) is a single batched call.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import joblib
import numpy as np

log = logging.getLogger("ml")


class AnomalyScorer:
    def __init__(self, model_path: str):
        self.path = Path(model_path)
        self.model = None
        self.anchors: tuple[list[float], list[float]] = ([0.0, 1.0], [0.0, 100.0])
        self.meta: dict = {}
        self.outage = False          # operator-triggered simulated outage (NFR-R1 demo)
        self.last_ms = 0.0

    # ------------------------------------------------------------------ lifecycle
    def load(self, auto_train: bool = True) -> bool:
        if not self.path.exists():
            if not auto_train:
                return False
            from .train import train_and_save

            log.info("model.pkl not found - training a new Isolation Forest on synthetic normal data")
            train_and_save(str(self.path))
        bundle = joblib.load(self.path)
        self.model = bundle["model"]
        self.anchors = (bundle["anchors_s"], bundle["anchors_pct"])
        self.meta = bundle.get("meta", {})
        self.warm_up()
        log.info("model loaded from %s (%s)", self.path, self.meta.get("trained_at", "?"))
        return True

    def warm_up(self) -> None:
        self.raw(np.zeros((1, 6)))

    @property
    def ready(self) -> bool:
        return self.model is not None

    # ------------------------------------------------------------------ scoring
    def raw(self, x: np.ndarray) -> np.ndarray:
        """Isolation-Forest anomaly score s in (0, 1); ~0.5 normal, -> 1 anomalous."""
        return -self.model.score_samples(x)

    def to_percent(self, s: np.ndarray) -> np.ndarray:
        xs, ys = self.anchors
        pct = np.interp(s, xs, ys)
        over = s > xs[-1]
        if np.any(over):   # gentle extrapolation beyond the last anchor
            pct = np.where(over, ys[-1] + (s - xs[-1]) * 150.0, pct)
        return np.clip(pct, 0.0, 100.0)

    def score(self, x: np.ndarray) -> np.ndarray:
        """Batched inference. Raises if the model is unavailable (caller keeps the last score)."""
        if self.outage or self.model is None:
            raise RuntimeError("ML service unavailable")
        t0 = time.perf_counter()
        pct = self.to_percent(self.raw(x))
        self.last_ms = (time.perf_counter() - t0) * 1000.0
        return pct
