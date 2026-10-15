"""API contract, auth, fault -> alert flow and WebSocket smoke tests (real app, in-process)."""
import time

from tests.conftest import AUTH


def wait(fn, timeout=30, every=0.3):
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = fn()
        if v:
            return v
        time.sleep(every)
    return None


def test_health_machines_config(client):
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["storage_mode"] == "memory" and h["ml_ready"]
    assert wait(lambda: all(m["live"] for m in client.get("/machines").json()), 10)
    ms = client.get("/machines").json()
    assert {m["id"] for m in ms} == {"CNC-01", "Press-02", "Conveyor-03", "Welder-04", "Packer-05"}
    cfg = client.get("/config").json()
    assert cfg["anomaly_threshold"] == 85 and cfg["technicians"]


def test_openapi_docs(client):
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    for p in ("/alerts", "/oee", "/maintenance", "/whatif/{machine_id}", "/simulator/inject-fault", "/reports/oee-trend"):
        assert p in paths


def test_oee_endpoint(client):
    assert wait(lambda: client.get("/oee?window=1h").status_code == 200, 10)
    d = client.get("/oee?window=8h").json()
    assert 0 <= d["plant"]["oee"] <= 100 and len(d["machines"]) == 5
    assert client.get("/oee?window=2h").status_code == 422


def test_telemetry_history_and_errors(client):
    wait(lambda: len(client.get("/machines/CNC-01/telemetry?max_points=50").json()["points"]) > 3, 10)
    pts = client.get("/machines/CNC-01/telemetry").json()["points"]
    assert pts and {"ts", "temperature", "vibration", "status", "cycle_count"} <= set(pts[0])
    assert client.get("/machines/NOPE/telemetry").status_code == 404
    assert client.get("/machines/CNC-01/telemetry?from=garbage").status_code == 422


def test_write_endpoints_require_auth(client):
    assert client.post("/alerts/1/ack").status_code == 401
    assert client.post("/maintenance", json={"machine_id": "CNC-01", "action": "x1"}).status_code == 401
    assert client.post("/simulator/inject-fault", json={"machine_id": "CNC-01", "kind": "stop"}).status_code == 401
    assert client.post("/auth/login", auth=("manager", "wrong")).status_code == 401
    assert client.post("/auth/login", auth=AUTH).json()["role"] == "floor_manager"
    r = client.post("/alerts/1/ack", headers={"X-Requested-With": "fetch"})
    assert r.status_code == 401 and "www-authenticate" not in r.headers


def test_ingest_validation_rejects_bad_payloads(client):
    good = {"machine_id": "CNC-01", "temperature": 60, "vibration": 2, "status": "RUNNING", "cycle_count": 1}
    assert client.post("/telemetry", json={**good, "temperature": -4}).status_code == 422
    assert client.post("/telemetry", json={**good, "status": "BROKEN"}).status_code == 422
    assert client.post("/telemetry", json={**good, "machine_id": "Ghost-99"}).status_code == 422


def test_maintenance_crud(client):
    r = client.post("/maintenance", auth=AUTH, json={"machine_id": "Packer-05", "action": "Replace belt", "notes": "n", "technician": "A. Kulkarni"})
    assert r.status_code == 201
    rid = r.json()["id"]
    assert any(x["id"] == rid for x in client.get("/maintenance?machine_id=Packer-05").json())
    assert client.patch(f"/maintenance/{rid}", auth=AUTH, json={"status": "closed"}).json()["status"] == "closed"
    assert client.post("/maintenance", auth=AUTH, json={"machine_id": "Nope", "action": "xx"}).status_code == 404
    assert client.delete(f"/maintenance/{rid}", auth=AUTH).status_code == 204
    assert client.delete(f"/maintenance/{rid}", auth=AUTH).status_code == 404


def test_red_alert_flow_ack_feedback(client):
    assert client.post("/simulator/inject-fault", auth=AUTH, json={"machine_id": "Press-02", "kind": "vib_spike", "duration_s": 20}).status_code == 200
    red = wait(lambda: [a for a in client.get("/alerts?level=red&machine_id=Press-02").json() if a["kind"] == "vib_high"], 20)
    assert red, "a vibration spike should raise a Red alert"
    aid = red[0]["id"]
    assert client.post(f"/alerts/{aid}/ack", auth=AUTH).json()["status"] == "acknowledged"
    assert client.post(f"/alerts/{aid}/assign", auth=AUTH, json={"technician": "S. Patil"}).json()["technician"] == "S. Patil"
    fb = client.post(f"/alerts/{aid}/feedback", auth=AUTH, json={"verdict": "true_positive"}).json()
    assert fb["feedback"]["verdict"] == "true_positive"
    assert client.post(f"/alerts/{aid}/feedback", auth=AUTH, json={"verdict": "maybe"}).status_code == 422
    assert client.post(f"/alerts/{aid}/resolve", auth=AUTH, json={"notes": "bolt tightened"}).json()["status"] == "resolved"
    assert client.get("/alerts/99999").status_code == 404
    client.post("/simulator/clear", auth=AUTH, json={})


def test_whatif_endpoint_and_reports(client):
    w = client.get("/whatif/CNC-01").json()
    assert w["equation"] and "projection" in w and w["threshold"] == 85
    assert client.get("/whatif/NOPE").status_code == 404
    assert client.get("/reports/oee-trend").status_code == 200
    assert "rows" in client.get("/reports/downtime").json()
    assert "precision" in client.get("/reports/ml-accuracy").json()


def test_ml_outage_keeps_serving(client):
    assert client.post("/ml/outage", auth=AUTH, json={"enabled": True}).status_code == 200
    time.sleep(1.5)
    assert all(m["live"]["ml_ok"] is False for m in client.get("/machines").json() if m["live"])
    assert client.get("/metrics").json()["ml"]["outage"] is True
    client.post("/ml/outage", auth=AUTH, json={"enabled": False})
    assert wait(lambda: all(m["live"]["ml_ok"] for m in client.get("/machines").json() if m["live"]), 8)


def test_metrics_and_websocket(client):
    with client.websocket_connect("/ws/live") as ws:
        assert ws.receive_json()["type"] == "hello"
        msgs = [ws.receive_json() for _ in range(3)]
        snaps = [m for m in msgs if m["type"] == "snapshot"]
        assert snaps and len(snaps[0]["machines"]) == 5 and "plant" in snaps[0]
        assert {"oee", "anomaly_score", "level"} <= set(snaps[0]["machines"][0])
    m = client.get("/metrics").json()
    assert m["inference_ms"]["max"] is None or m["inference_ms"]["max"] < 200


# ---------------------------------------------------------------- roles, throttling, headers
def test_role_permissions(client):
    analyst, engineer = ("analyst", "analyst123"), ("engineer", "engineer123")
    r = client.post("/maintenance", auth=analyst, json={"machine_id": "CNC-01", "action": "Check belt"})
    assert r.status_code == 403 and "Production Analyst" in r.json()["detail"]
    assert client.post("/alerts/1/ack", auth=analyst).status_code == 403
    r = client.post("/simulator/inject-fault", auth=engineer, json={"machine_id": "CNC-01", "kind": "stop"})
    assert r.status_code == 403
    assert client.put("/machines/CNC-01/thresholds?temp_limit=86", auth=engineer).status_code == 403
    ok = client.post("/maintenance", auth=engineer, json={"machine_id": "CNC-01", "action": "Check belt"})
    assert ok.status_code == 201
    client.delete(f"/maintenance/{ok.json()['id']}", auth=engineer)


def test_login_throttle_locks_after_repeated_failures(client):
    for _ in range(5):
        assert client.post("/auth/login", auth=("admin", "nope")).status_code == 401
    r = client.post("/auth/login", auth=("admin", "nope"))
    assert r.status_code == 429 and "Retry-After" in r.headers
    assert client.post("/auth/login", auth=("admin", "admin123")).status_code == 429   # still locked for this user
    assert client.post("/auth/login", auth=("manager", "manager123")).status_code == 200  # other users unaffected


def test_security_headers(client):
    h = client.get("/health").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
