"""Unit tests: OEE maths, rule engine, What-If regression, ML scoring, alert lifecycle, validation."""
import time

import numpy as np
import pytest

from app.schemas import TelemetryIn
from app.services import whatif
from app.services.alerts import AlertManager
from app.services.oee import MachineOEE, compute_oee
from app.services.rules import Condition, evaluate_rules


# ---------------------------------------------------------------- OEE
def test_oee_formula_exact():
    # 100 s planned, 90 s running, 40 cycles x 2 s ideal = 80 s, 38 good of 40
    o = compute_oee([100, 90, 80, 40, 38, 0])
    assert o["availability"] == 90.0
    assert o["performance"] == pytest.approx(88.89, abs=0.01)
    assert o["quality"] == 95.0
    assert o["oee"] == pytest.approx(0.9 * (80 / 90) * 0.95 * 100, abs=0.01)


def test_oee_performance_capped_and_empty_safe():
    assert compute_oee([10, 10, 50, 5, 5, 0])["performance"] == 100.0
    assert compute_oee([0, 0, 0, 0, 0, 0])["oee"] == 0.0


def test_machine_oee_accumulates_and_handles_counter_reset():
    m = MachineOEE(ideal_cycle_s=2.0)
    t = 1_000_000.0
    cyc = good = 0
    for i in range(120):                      # 60 s running, 1 cycle / 2 s, 1 reject in 10
        t += 0.5
        if i % 4 == 3:
            cyc += 1
            good += 0 if cyc % 10 == 0 else 1
        m.update(t, "RUNNING", cyc, good)
    for _ in range(40):                       # 20 s idle
        t += 0.5
        m.update(t, "IDLE", cyc, good)
    r = m.result()["1h"]
    assert r["availability"] == pytest.approx(75.0, abs=2)
    assert r["quality"] == pytest.approx(90.0, abs=3)
    m.update(t + 0.5, "RUNNING", 0, 0)        # simulator restarted: counters reset, must not go negative
    assert m.result()["1h"]["cycles"] >= 0


def test_oee_windows_roll_off():
    m = MachineOEE(1.0)
    t = 0.0
    for _ in range(int(2 * 3600 / 5)):        # 2 h of 5 s samples, running
        t += 5
        m.update(t, "RUNNING", int(t), int(t))
    assert m.windows["1h"].totals[0] == pytest.approx(3600, rel=0.02)
    assert m.windows["8h"].totals[0] == pytest.approx(7200, rel=0.02)


# ---------------------------------------------------------------- rules
def test_rules_thresholds():
    assert evaluate_rules(85, 7, 70, 2, "RUNNING") == []
    assert {c.kind for c in evaluate_rules(85, 7, 86, 8, "RUNNING")} == {"temp_high", "vib_high"}
    assert [c.kind for c in evaluate_rules(85, 7, 60, 1, "STOPPED")] == ["machine_down"]
    assert evaluate_rules(85, 7, 85.0, 7.0, "RUNNING") == []   # strictly greater than


# ---------------------------------------------------------------- What-If
def test_fit_line_recovers_slope():
    pts = [(t, 60 + 0.1 * t) for t in range(0, 180)]
    m, c, r2 = whatif.fit_line(pts)
    assert m == pytest.approx(0.1, abs=1e-6) and c == pytest.approx(60, abs=1e-6) and r2 == pytest.approx(1.0)


def test_projection_orange_within_horizon():
    # 60 -> 78 degC over 180 s (0.1 C/s); limit 85 -> ETA ~70 s: not yet orange (horizon 60 s)
    pts = [(1000 + t, 60 + 0.1 * t) for t in range(180)]
    p = whatif.project(pts, 1179, 85)
    assert p["ready"] and not p["projected"] and 60 < p["eta_s"] < 80
    pts += [(1180 + t, 78 + 0.1 * t) for t in range(15)]     # 15 s later the ETA is ~55 s -> orange
    p = whatif.project(pts[-180:], 1194, 85)
    assert p["projected"] and 0 < p["eta_s"] <= 60


def test_projection_ignores_flat_noise_and_short_windows():
    rng = np.random.default_rng(1)
    flat = [(t, 62 + float(rng.normal(0, 0.4))) for t in range(180)]
    assert not whatif.project(flat, 179, 85)["projected"]
    assert not whatif.project(flat[:10], 9, 85)["ready"]


# ---------------------------------------------------------------- ML
def test_ml_scores_normal_low_and_fault_high_fast():
    from app.config import get_settings
    from app.ml.features import StreamFeatures
    from app.ml.scorer import AnomalyScorer
    from simulator import Factory, build_profiles

    sc = AnomalyScorer(get_settings().model_path)
    assert sc.load()
    prof = build_profiles(1)[0]
    f = Factory([prof], seed=5, start_ts=0)
    sf = StreamFeatures(prof.base_temp, prof.base_vib, prof.temp_scale, prof.vib_scale, prof.vib_noise)
    healthy, faulty = [], []
    ts = 0.0
    for i in range(1200):
        ts += 0.5
        if i == 600:
            f.inject(prof.id, "anomaly", ts, 120)
        s = f.step(0.5, ts)[0]
        sf.push(ts, s["temperature"], s["vibration"], s["status"] == "RUNNING")
        if sf.clean and i > 40:
            score = float(sc.score(np.array([sf.vector(s["temperature"], s["vibration"])]))[0])
            if i < 600:
                healthy.append(score)
            elif 640 < i < 840:
                faulty.append(score)
    assert np.percentile(healthy, 99) < 85
    assert np.median(faulty) > 85
    assert sc.last_ms < 200


def test_ml_outage_raises():
    from app.config import get_settings
    from app.ml.scorer import AnomalyScorer

    sc = AnomalyScorer(get_settings().model_path)
    sc.load()
    sc.outage = True
    with pytest.raises(RuntimeError):
        sc.score(np.zeros((1, 6)))


# ---------------------------------------------------------------- alerts
def _cond(kind, level):
    return Condition(kind, level, kind, kind, 1.0, 1.0)


def test_alert_lifecycle_debounce_and_escalation():
    am = AlertManager()
    t = time.time()
    assert am.update("M", [_cond("ml_anomaly", "yellow")], t) == "green"            # needs 2 ticks
    assert am.update("M", [_cond("ml_anomaly", "yellow")], t + .5) == "yellow"
    assert am.update("M", [_cond("projected_fault", "orange")], t + 1) == "yellow"  # orange not open yet: no green flash
    assert am.update("M", [_cond("projected_fault", "orange")], t + 1.5) == "orange"  # opens, supersedes yellow
    assert am.update("M", [_cond("temp_high", "red")], t + 2) == "red"              # red is immediate
    by_level = {a.level: a for a in am.alerts.values()}
    assert not by_level["yellow"].active and by_level["red"].active
    lvl = "red"
    for k in range(10):                                                              # clears after 3 s
        lvl = am.update("M", [], t + 3 + k)
    assert lvl == "green" and not by_level["red"].active


def test_alert_ack_resolve_feedback():
    am = AlertManager()
    am.update("M", [_cond("temp_high", "red")], 1.0)
    a = next(iter(am.alerts.values()))
    am.acknowledge(a.id, "bob")
    assert a.status == "acknowledged" and a.acked_by == "bob"
    am.assign(a.id, "Tech", "bob")
    assert a.technician == "Tech"
    am.feedback(a.id, "bob", "true_positive", "ok")
    assert a.feedback["verdict"] == "true_positive"
    am.resolve(a.id, "bob", "fixed")
    assert a.status == "resolved" and a.resolution_notes == "fixed"
    with pytest.raises(KeyError):
        am.acknowledge(999, "bob")


# ---------------------------------------------------------------- validation (FR-09)
@pytest.mark.parametrize("bad", [
    {"temperature": -5}, {"status": "EXPLODING"}, {"vibration": -1}, {"cycle_count": -3}, {"machine_id": "bad id!"},
])
def test_telemetry_validation_rejects(bad):
    good = {"machine_id": "CNC-01", "temperature": 60, "vibration": 2, "status": "RUNNING", "cycle_count": 5}
    TelemetryIn(**good)
    with pytest.raises(Exception):
        TelemetryIn(**{**good, **bad})
