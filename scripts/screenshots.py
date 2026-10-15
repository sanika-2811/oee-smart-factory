"""Capture real screenshots of the running dashboard with Playwright (visual QA + report/PPT figures).

Prerequisites: backend on :8000 and the frontend on :5173 (``make dev`` / scripts/dev.ps1), plus
    pip install playwright && python -m playwright install chromium

    python scripts/screenshots.py --out docs/screenshots            # desktop 1440 px  (+ 390 px mobile with --mobile)
"""
from __future__ import annotations

import argparse
import base64
import json
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

API = "http://127.0.0.1:8000"
APP = "http://127.0.0.1:5173"
AUTH = "Basic " + base64.b64encode(b"manager:manager123").decode()


def api(path: str, body: dict | None = None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None,
                                 method="POST" if body is not None else "GET")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", AUTH)
    with urllib.request.urlopen(req, timeout=10) as r:
        raw = r.read()
        return json.loads(raw) if raw else None


def wait_levels(wanted: set[str], timeout: float) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        m = api("/machines")
        got = {x["live"]["level"] for x in m if x["live"]}
        if wanted <= got:
            return True
        time.sleep(1)
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/screenshots")
    ap.add_argument("--mobile", action="store_true", help="also capture 390 px mobile views")
    ap.add_argument("--quick", action="store_true", help="skip the fault scenario (layout QA only)")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        sizes = [("desktop", 1440, 900)] + ([("mobile", 390, 844)] if args.mobile else [])
        pages = {}
        for name, w, h in sizes:
            ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1 if w > 800 else 2, color_scheme="dark")
            pg = ctx.new_page()
            pg.on("console", lambda m: print("  [console]", m.text[:200]) if m.type == "error" else None)
            pages[name] = pg

        def shot(name: str, route: str, wait: float = 1.8, full: bool = False, pre=None) -> None:
            for sz, pg in pages.items():
                pg.goto(f"{APP}/#{route}")
                pg.wait_for_timeout(int(wait * 1000))
                if pre:
                    pre(pg)
                pg.screenshot(path=str(out / f"{sz}_{name}.png"), full_page=full)
                print("saved", out / f"{sz}_{name}.png")

        # ---- calm state
        api("/simulator/clear", {})
        api("/simulator/speed", {"factor": 1})
        time.sleep(2)
        shot("01_overview_normal", "/overview", full=True)
        shot("02_machines_normal", "/machines", full=True)

        if not args.quick:
            # ---- scenario: Yellow (ML), Red (rule), Orange (What-If projection)
            api("/simulator/speed", {"factor": 6})              # 3-min ramp -> 30 s
            api("/simulator/inject-fault", {"machine_id": "Welder-04", "kind": "anomaly", "duration_s": 120})
            api("/simulator/inject-fault", {"machine_id": "CNC-01", "kind": "temp_ramp"})
            api("/simulator/inject-fault", {"machine_id": "Press-02", "kind": "vib_spike", "duration_s": 120})
            print("waiting for Yellow + Red ...")
            wait_levels({"yellow", "red"}, 40)
            # Orange appears roughly 20 s into the (compressed) ramp
            t0 = time.time()
            while time.time() - t0 < 45:
                lv = {x["id"]: x["live"]["level"] for x in api("/machines") if x["live"]}
                if lv.get("CNC-01") == "orange":
                    break
                time.sleep(0.5)
            shot("03_overview_alerts", "/overview", wait=1.2, full=True)
            shot("04_machines_alerts", "/machines", wait=1.0, full=True)
            shot("05_machine_detail_whatif", "/machines/CNC-01", wait=2.5, full=True)
            shot("06_alerts_centre", "/alerts", wait=1.5, full=True)
            # ---- operator workflow: acknowledge, feedback, maintenance
            alerts = api("/alerts?limit=50")
            yellow = next((a for a in alerts if a["level"] == "yellow"), None)
            red = next((a for a in alerts if a["level"] == "red"), None)
            if red:
                api(f"/alerts/{red['id']}/ack", {})
                api(f"/alerts/{red['id']}/assign", {"technician": "A. Kulkarni"})
                api("/maintenance", {"machine_id": red["machine_id"], "alert_id": red["id"], "action": "Inspect hydraulic mount and tighten bolts",
                                     "notes": "Vibration spike traced to a loose mounting bolt; torqued to spec.", "technician": "A. Kulkarni", "status": "in_progress"})
            if yellow:
                api(f"/alerts/{yellow['id']}/feedback", {"verdict": "true_positive", "comment": "Bearing noise confirmed"})
            api("/maintenance", {"machine_id": "Conveyor-03", "action": "Replace conveyor belt tensioner", "notes": "Scheduled preventive maintenance.",
                                 "technician": "R. Deshmukh", "status": "closed"})
            time.sleep(1.5)
            shot("07_alerts_centre_actioned", "/alerts", wait=1.5, full=True)
            shot("08_maintenance", "/maintenance", wait=1.5, full=True)
        shot("09_reports", "/reports", wait=2.5, full=True)
        shot("10_control", "/control", wait=2.5, full=True)

        # ---- light theme + login dialog
        if "desktop" in pages:
            pg = pages["desktop"]
            pg.goto(f"{APP}/#/overview")
            pg.wait_for_timeout(1500)
            pg.click("button[aria-label^='Switch to light']")
            pg.wait_for_timeout(1200)
            pg.screenshot(path=str(out / "desktop_11_light_theme.png"), full_page=True)
            pg.click("button[aria-label^='Switch to dark']")
            pg.click("text=Sign in")
            pg.wait_for_timeout(500)
            pg.screenshot(path=str(out / "desktop_12_login.png"))
            print("saved light theme + login")
        if not args.quick:
            api("/simulator/clear", {})
            api("/simulator/speed", {"factor": 1})
        browser.close()


if __name__ == "__main__":
    main()
