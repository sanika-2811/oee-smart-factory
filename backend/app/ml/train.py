"""Offline training:  ``python -m app.ml.train``

1. Generate synthetic *normal* telemetry by running the virtual factory with no faults.
2. Fit an Isolation Forest on normalised features.
3. Calibrate raw scores to a 0-100 % Anomaly Score (anchors: normal median -> 8 %,
   normal 99.9th percentile -> 70 %, median injected-anomaly -> 95 %).
4. Validate against injected faults on an independent run and log precision/recall.
5. Save ``model.pkl`` (+ ``model_meta.json``).
"""
from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from ..config import get_settings
from .features import FEATURE_NAMES, batch_features

log = logging.getLogger("ml.train")
STEP = 0.5


def _run_factory(profiles, seconds: float, seed: int, schedule: dict | None = None):
    """Return {machine_id: (temps, vibs, status_is_running, fault_label)} sampled every STEP seconds."""
    from simulator import Factory

    f = Factory(profiles, seed=seed, start_ts=0.0)
    n = int(seconds / STEP)
    ids = list(f.machines)
    data = {m: ([], [], [], []) for m in ids}
    events = sorted((schedule or {}).items())  # [(t, [(machine, kind, duration)])]
    ev_i = 0
    for i in range(n):
        ts = i * STEP
        while ev_i < len(events) and events[ev_i][0] <= ts:
            for mid, kind, dur in events[ev_i][1]:
                f.inject(mid, kind, ts, dur)
            ev_i += 1
        for s in f.step(STEP, ts):
            mid = s["machine_id"]
            t, v, run, lab = data[mid]
            t.append(s["temperature"]); v.append(s["vibration"]); run.append(s["status"] == "RUNNING")
            m = f.machines[mid]
            if any(fl.active(ts) and ts - fl.start > 8 for fl in m.faults.values()):
                lab.append(1)
            elif m.faults or ts < m.last_fault_end + 45:
                lab.append(-1)      # ramp-in / cool-down: neither clearly normal nor faulty
            else:
                lab.append(0)
            if m.faults:
                m.last_fault_end = max(fl.start + fl.duration for fl in m.faults.values())
    return {k: tuple(np.array(x) for x in v) for k, v in data.items()}


def _features(profiles, data):
    by_id = {p.id: p for p in profiles}
    X, run_mask, labels, mids = [], [], [], []
    for mid, (t, v, run, lab) in data.items():
        feats, clean = batch_features(t, v, run, by_id[mid], STEP)
        X.append(feats)
        run_mask.append(run & clean); labels.append(lab); mids.append(np.full(len(t), mid))
    return np.vstack(X), np.concatenate(run_mask), np.concatenate(labels), np.concatenate(mids)


def train_and_save(model_path: str, hours: float = 1.5, seed: int = 42, validate: bool = True) -> dict:
    from simulator import build_profiles

    t0 = time.time()
    profiles = build_profiles(20)
    data = _run_factory(profiles, hours * 3600, seed)
    X, run, _, _ = _features(profiles, data)
    X = X[run][::3]                                    # RUNNING samples, thinned for speed
    # drop the first 30 s of each machine's warm-up transient implicitly via thinning; fit
    # Trimmed fit: score once, drop the 0.3 % most extreme "normal" rows (noise spikes, start-up
    # transients) and refit, so the model's notion of normal is tight.
    model = IsolationForest(n_estimators=200, max_samples=1024, contamination="auto", random_state=seed, n_jobs=1)
    model.fit(X)
    s0 = -model.score_samples(X)
    X = X[s0 <= np.percentile(s0, 99.7)]
    model.fit(X)
    s_norm = -model.score_samples(X)

    # --- anchors: synthetic anomalies at the strength of the 'anomaly' what-if scenario
    sched = {}
    for i, p in enumerate(profiles):
        sched.setdefault(60.0 + 5 * (i % 4), []).append((p.id, "anomaly", 240.0))
    adata = _run_factory(profiles, 330, seed + 1, sched)
    AX, arun, alab, _ = _features(profiles, adata)
    s_anom = -model.score_samples(AX[(alab == 1) & arun])
    xs = [float(np.percentile(s_norm, 50)), float(np.percentile(s_norm, 99.9)), float(np.median(s_anom))]
    xs[1] = max(xs[1], xs[0] + 1e-3)
    xs[2] = max(xs[2], xs[1] + 0.02)
    ys = [8.0, 70.0, 95.0]

    meta = {
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "algorithm": "IsolationForest(n_estimators=200, max_samples=1024), trimmed refit",
        "features": FEATURE_NAMES,
        "training_rows": int(len(X)),
        "training_data": f"{hours} h of synthetic normal telemetry x {len(profiles)} machine profiles",
        "anchors_s": xs, "anchors_pct": ys, "threshold_pct": get_settings().anomaly_threshold,
        "train_seconds": round(time.time() - t0, 1),
    }
    bundle = {"model": model, "anchors_s": xs, "anchors_pct": ys, "meta": meta}
    if validate:
        meta["validation"] = validate_model(bundle, profiles, seed + 2)
    path = Path(model_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path)
    path.with_name("model_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log.info("model saved to %s in %.1fs | validation: %s", path, time.time() - t0, meta.get("validation"))
    return meta


def validate_model(bundle: dict, profiles, seed: int, threshold: float | None = None) -> dict:
    """Precision/recall style sanity metrics against injected faults on an independent run."""
    threshold = threshold or get_settings().anomaly_threshold
    model, xs, ys = bundle["model"], bundle["anchors_s"], bundle["anchors_pct"]
    profs = profiles[:10]
    sched: dict[float, list] = {}
    plan = []
    for i, p in enumerate(profs):
        if i < 6:
            kind, dur = ("anomaly", 45.0) if i % 2 == 0 else ("vib_spike", 25.0)
            at = 200.0 + 70 * (i // 2)
            sched.setdefault(at, []).append((p.id, kind, dur))
            plan.append((p.id, kind, at, dur))
    seconds = 800
    data = _run_factory(profs, seconds, seed, sched)
    X, run, lab, mids = _features(profs, data)
    pct = np.clip(np.interp(-model.score_samples(X), xs, ys), 0, 100)
    flagged = (pct > threshold) & run
    tp = int(np.sum(flagged & (lab == 1))); fp = int(np.sum(flagged & (lab == 0)))
    fn = int(np.sum(~flagged & (lab == 1) & run))
    healthy = np.array([m not in {p[0] for p in plan} for m in mids]) & run
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    n = len(data[profs[0].id][0])
    detected = 0
    for mid, kind, at, dur in plan:
        sel = (mids == mid)
        series = flagged[sel]
        i0, i1 = int(at / STEP), int((at + dur) / STEP)
        window = series[i0:i1]
        if np.any(window[1:] & window[:-1]):
            detected += 1
    normal_hours = (healthy.sum() * STEP) / 3600.0
    fp_per_hour = float(np.sum(flagged & healthy) / normal_hours) if normal_hours else 0.0
    return {
        "threshold_pct": threshold, "sample_precision": round(precision, 4), "sample_recall": round(recall, 4),
        "faults_injected": len(plan), "faults_detected": detected,
        "event_recall": round(detected / len(plan), 3) if plan else None,
        "false_alarm_samples_per_hour_on_healthy_machines": round(fp_per_hour, 2),
        "samples_evaluated": int(len(pct)),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    meta = train_and_save(get_settings().model_path)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    sys.exit(main())
