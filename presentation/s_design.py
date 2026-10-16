"""Slides 10-29: architecture, data flow, DFDs, method, modules, stack, OEE/alerts/ML/What-If, UML, database, deployment."""
from __future__ import annotations

import math

from pptx.chart.data import CategoryChartData, XyChartData
from pptx.enum.chart import XL_AXIS_CROSSES, XL_CHART_TYPE, XL_LEGEND_POSITION, XL_MARKER_STYLE
from pptx.oxml.ns import qn
from pptx.util import Pt

from deckkit import *  # noqa: F401,F403


def _white_label(s, cx, cy, w, text, size=12, h=0.26):
    """Label with a white plate so it stays readable on top of a line."""
    b = box(s, cx - w / 2, cy - h / 2, w, h, text, fill="white", edge=None, size=size, color=MUTED, margin=0.03, radius=0.04)
    b.line.fill.background()
    return b


def _ellipse_pt(cx, cy, rx, ry, tx, ty):
    dx, dy = tx - cx, ty - cy
    k = 1.0 / math.sqrt((dx / rx) ** 2 + (dy / ry) ** 2)
    return cx + dx * k, cy + dy * k


def build(ctx):
    new = ctx.new

    # ================================================================== 10  architecture
    s = new("System Architecture",
            "Walk left to right: the simulator publishes JSON over MQTT (WebSockets) to Mosquitto; the FastAPI backend validates, computes OEE and runs the three detectors, "
            "stores data and pushes a snapshot every 500 ms to the React dashboard. Two switches in .env choose the ingest path (direct or mqtt) and the storage (memory or db).")
    bx = X0 + 4.8
    box(s, bx, 1.1, 3.75, 4.1, "", fill="grey", edge="blue", dash=True, line=2)
    tb(s, bx + 0.15, 1.18, 3.45, 0.35, "FastAPI backend (asyncio)", size=16, bold=True, color=EDGE["blue"])
    mods = [("Ingest + validation", "FR-09", "blue"), ("OEE engine", "FR-02 · A × P × Q", "green"), ("Rule engine → RED", "FR-03", "red"),
            ("Isolation Forest → YELLOW", "FR-04", "yellow"), ("What-If trend → ORANGE", "FR-07", "orange"), ("Alerts, maintenance, API", "FR-05 · FR-06", "violet")]
    mw = (3.75 - 0.2 - 0.15) / 2
    for i, (t, fr, col) in enumerate(mods):
        mx = bx + 0.1 + (i % 2) * (mw + 0.15)
        my = 1.65 + (i // 2) * 1.17
        box(s, mx, my, mw, 1.05, [{"text": t, "size": 13, "bold": True}, {"text": fr, "size": 12, "color": MUTED}], fill=col, edge=col, margin=0.08)
    side = [("Virtual Factory Simulator", "5–20 machines · every 500 ms", X0, 1.55, "blue"), ("Eclipse Mosquitto", "MQTT over WebSockets", X0 + 2.4, 1.55, "orange"),
            ("React 18 dashboard", "Chart.js 2D charts", X0 + 9.4, 1.55, "cyan")]
    for t, d, x, w, col in side:
        box(s, x, 2.3, w, 1.7, [{"text": t, "size": 14, "bold": True}, {"text": d, "size": 12}], fill=col, edge=col, margin=0.08)
    ym = 3.0
    for x1, x2, lab in [(X0 + 1.55, X0 + 2.4, "MQTT"), (X0 + 3.95, X0 + 4.8, "subscribe"), (X0 + 8.55, X0 + 9.4, "WebSocket")]:
        line(s, x1 + 0.02, ym, x2 - 0.02, ym, color=INK, w=2)
        label(s, x1, ym - 0.32, x2 - x1, lab, size=12)
    for x1, x2, lab in [(X0 + 2.4, X0 + 1.55, "faults"), (X0 + 4.8, X0 + 3.95, "control"), (X0 + 9.4, X0 + 8.55, "REST")]:
        line(s, x1 - 0.02, 3.6, x2 + 0.02, 3.6, color=SLATE, w=1.5, dash=True)
        label(s, min(x1, x2), 3.64, abs(x2 - x1), lab, size=12)
    tb(s, X0 + 9.4, 4.15, 1.55, 0.5, "Chrome · Edge · Firefox", size=12, color=MUTED, align="c")
    for x, nm, d in [(bx, "InfluxDB v2", "telemetry_raw 30 d\ntelemetry_agg 1 y"), (bx + 1.95, "PostgreSQL 14", "machines · users · alerts\nmaintenance · feedback")]:
        line(s, x + 0.9, 5.2, x + 0.9, 5.8, color=INK, w=2)
        box(s, x, 5.8, 1.8, 1.05, [{"text": nm, "size": 14, "bold": True}] + [{"text": t, "size": 12} for t in d.split("\n")], fill="cyan", edge="cyan", margin=0.05)
    box(s, X0, 5.55, 4.4, 1.3, [{"text": "Two switches in .env", "size": 14, "bold": True},
                                {"text": "INGEST_MODE = direct | mqtt", "size": 13}, {"text": "STORAGE_MODE = memory | db", "size": 13},
                                {"text": "→ runs with no Docker and no database", "size": 13, "italic": True, "color": MUTED}], fill="grey", edge="white", align="l", margin=0.2)

    # ================================================================== 14  methodology
    s = new("Methodology",
            "An incremental, requirements-driven approach: SRS first, then design, then build in ten milestones, verify, and deploy and document. "
            "Each milestone ended with working code and passing tests - that is the Definition of Done from SRS section 13.2.")
    phases = [("1  Requirements", "blue", ["SRS: 12 functional and 18 non-functional requirements", "6 user stories, 8 use cases", "Constraints C-01 to C-07"]),
              ("2  Design", "cyan", ["Architecture and data-flow diagrams", "UML: use case, class, sequence, activity", "Database schema"]),
              ("3  Build", "green", ["Ten incremental milestones (M1 – M10)", "Simulator → backend → ML → What-If → dashboard", "Docker Compose, scripts"]),
              ("4  Verify", "orange", ["45 automated tests", "13-check end-to-end smoke test", "Accessibility, 3 browsers, live databases"]),
              ("5  Document", "violet", ["Project report and this presentation", "README, setup guides", "Auto-generated API docs at /docs"])]
    cs5 = cols(5, gap=0.2)
    for (x, w), (t, col, bl) in zip(cs5, phases):
        shp = s.shapes.add_shape(MSO_SHAPE.CHEVRON, E(x), E(1.2), E(w + 0.22), E(0.95))
        shp.shadow.inherit = False
        shp.fill.solid()
        shp.fill.fore_color.rgb = EDGE[col]
        shp.line.fill.background()
        shp.adjustments[0] = 0.28
        tf = shp.text_frame
        tf.margin_left, tf.margin_right = E(0.28), E(0.02)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        _fill_paras = __import__("deckkit")._fill_paras
        _fill_paras(tf, [{"text": t, "size": 13, "bold": True}], 13, True, WHITE, "l", False)
        box(s, x, 2.4, w, 3.35, "", fill=col, edge=col)
        tb(s, x + 0.15, 2.55, w - 0.3, 3.1, [{"text": b, "size": 15, "bullet": True, "space_after": 10} for b in bl], size=15)
    box(s, X0, 6.0, W, 0.8, "Every milestone ended with working code and passing tests – the Definition of Done in SRS §13.2", fill="grey", edge="white", size=16, bold=True, color=GREEN_D)

    # ================================================================== 15  modules
    s = new("Modules (SRS §3.2)",
            "The eight modules from the SRS, each with the file where it lives, so every module can be shown in the code if asked.")
    mods8 = [("Virtual Factory Simulator", "Emulates 5–20 machines; emits temperature, vibration, status and cycles every 500 ms.", "simulator/core.py", "blue"),
             ("OEE Calculation Engine", "Availability × Performance × Quality over rolling 1 h and 8 h windows.", "backend/app/services/oee.py", "green"),
             ("Rule-Based Alert Engine", "Deterministic hard limits raise Red alerts instantly.", "backend/app/services/rules.py", "red"),
             ("ML Anomaly Scorer", "Pre-trained Isolation Forest returns a 0–100 % anomaly score.", "backend/app/ml/scorer.py", "yellow"),
             ("Interactive 2D Dashboard", "Machine grid, live charts, alert feed, ML gauges, reports, controls.", "frontend/src/pages/", "cyan"),
             ("Maintenance & Feedback Logger", "Acknowledge, assign technician, notes, resolve, ML feedback.", "backend/app/services/alerts.py", "violet"),
             ("What-If Degradation Simulator", "Injects a temperature rise and projects the crossing with y = mx + c.", "backend/app/services/whatif.py", "orange"),
             ("Historical Reporting API", "7-day OEE, downtime per shift and ML accuracy.", "backend/app/api/routes.py", "grey")]
    for i, (t, d, f, col) in enumerate(mods8):
        (x, w), y = cols(4)[i % 4], 1.2 + (i // 4) * 2.85
        box(s, x, y, w, 2.6, "", fill=col, edge=col)
        tb(s, x + 0.15, y + 0.12, w - 0.3, 0.7, t, size=16, bold=True)
        tb(s, x + 0.15, y + 0.85, w - 0.3, 1.25, d, size=13)
        tb(s, x + 0.15, y + 2.2, w - 0.3, 0.3, f, size=11, color=MUTED, italic=True)

    # ================================================================== 16  technology stack
    s = new("Technologies Used",
            "Each layer and the tool chosen for it, all taken from the SRS technology stack. Everything is open source.")
    rows = [("Data source", ["Python simulator", "paho-mqtt", "NumPy"], "blue"), ("Messaging", ["Eclipse Mosquitto 2", "MQTT over WebSockets"], "orange"),
            ("Backend", ["FastAPI", "Pydantic v2", "asyncio", "WebSocket", "OpenAPI / Swagger"], "green"),
            ("Intelligence", ["scikit-learn Isolation Forest", "NumPy", "Least-squares regression"], "yellow"),
            ("Storage", ["InfluxDB v2 (time series)", "PostgreSQL 14", "SQLAlchemy"], "cyan"),
            ("Frontend", ["React 18", "TypeScript", "Vite", "Chart.js"], "violet"),
            ("Deploy & quality", ["Docker Compose", "nginx", "pytest", "Vitest", "Playwright", "axe-core"], "grey")]
    rh, rg = 0.7, (5.8 - 7 * 0.7) / 6
    for i, (layer, chips, col) in enumerate(rows):
        y = 1.1 + i * (rh + rg)
        box(s, X0, y, 2.3, rh, layer, fill=col, edge=col, size=16, bold=True)
        x = X0 + 2.5
        for c in chips:
            cw = len(c) * 0.092 + 0.45
            box(s, x, y + 0.08, cw, rh - 0.16, c, fill="white", edge=col, size=14, line=1.75, margin=0.05)
            x += cw + 0.15

    # ================================================================== 18  alert decision flowchart
    s = new("Alert Decision Flow – Every 500 ms per Machine",
            "This is the heart of the system. Each reading goes through three questions in strict priority. Red is certain and immediate. Orange uses a regression line to predict a crossing within "
            "60 seconds. Yellow comes from the Isolation Forest when the score stays above 85 percent. Higher levels suppress lower ones, and every alert is handed to the alert manager.")
    dx, dw = X0, 4.7
    cx = dx + dw / 2
    box(s, cx - 1.8, 1.1, 3.6, 0.5, "Telemetry reading received and validated", fill="blue", edge="blue", size=14)
    qs = [("Temperature or vibration above its limit, or status STOPPED?", 1.8, "red", "RED", "Hard fault – rule engine, immediate", "FR-03"),
          ("Trend line reaches the limit within 60 s? (R² ≥ 0.6)", 3.2, "orange", "ORANGE", "Projected fault – with ETA countdown", "FR-07"),
          ("ML anomaly score above 85 % for 2 readings?", 4.6, "yellow", "YELLOW", "ML caution – Isolation Forest", "FR-04")]
    line(s, cx, 1.62, cx, 1.78, color=INK, w=2)
    for q, y, col, nm, d, fr in qs:
        dm = s.shapes.add_shape(MSO_SHAPE.FLOWCHART_DECISION, E(dx), E(y), E(dw), E(1.15))
        dm.shadow.inherit = False
        dm.fill.solid()
        dm.fill.fore_color.rgb = SOFT["grey"]
        dm.line.color.rgb = EDGE["grey"]
        dm.line.width = Pt(2)
        tb(s, dx + 0.85, y + 0.17, dw - 1.7, 0.81, q, size=13, align="c", anchor="m")
        line(s, dx + dw + 0.02, y + 0.575, dx + dw + 0.78, y + 0.575, color=INK, w=2)
        label(s, dx + dw + 0.02, y + 0.25, 0.8, "yes", size=12, bold=True)
        box(s, dx + dw + 0.8, y + 0.125, 3.05, 0.9, [{"text": nm, "size": 16, "bold": True}, {"text": d, "size": 12}], fill=col, edge=col, line=2, margin=0.08)
        line(s, dx + dw + 3.87, y + 0.575, dx + dw + 4.37, y + 0.575, color=SLATE, w=1.5, dash=True)
    for y in (2.95, 4.35):
        line(s, cx, y + 0.01, cx, y + 0.24, color=INK, w=2)
        label(s, cx + 0.08, y - 0.01, 0.5, "no", size=12, bold=True, align="l")
    line(s, cx, 5.76, cx, 5.98, color=INK, w=2)
    label(s, cx + 0.08, 5.74, 0.5, "no", size=12, bold=True, align="l")
    box(s, cx - 1.8, 6.0, 3.6, 0.5, "GREEN – normal operation", fill="green", edge="green", size=14, bold=True)
    amx = dx + dw + 4.4
    box(s, amx, 1.8 + 0.125, X1 - amx, (4.6 + 1.15 - 1.8 - 0.25), [{"text": "Alert manager", "size": 15, "bold": True}, {"text": "acknowledge", "size": 13}, {"text": "assign", "size": 13},
                                                                    {"text": "resolve", "size": 13}, {"text": "ML feedback", "size": 13}], fill="violet", edge="violet", margin=0.05)
    tb(s, dx, 6.6, W, 0.3, "Higher levels suppress lower ones  ·  an alert clears when its condition is absent for 3 – 4 s", size=13, color=MUTED, italic=True)

    # ================================================================== 20  ML pipeline
    s = new("ML Anomaly Scoring – Isolation Forest",
            "Top lane: done once, offline. A synthetic dataset of normal behaviour trains an Isolation Forest; the raw model output is calibrated to a 0 to 100 percent score and saved as model.pkl. "
            "Bottom lane: every 500 ms the live reading is converted to the same features and scored; two readings above 85 percent raise a Yellow caution. "
            "Validated on injected faults: six of six detected, no false alarms. If the ML service fails, the last score is held and the red rules keep working.")
    lanes = [("Offline\n(once)", 1.2, [("Synthetic normal data", "68 687 rows · 20 machine profiles", "blue"), ("Feature engineering", "6 normalised features", "cyan"),
                                       ("Train Isolation Forest", "unsupervised – no fault labels needed", "violet"), ("Calibrate score", "mapped to 0–100 %, alert threshold 85 %", "yellow"),
                                       ("Save model.pkl", "loaded at start-up (C-04: trained once)", "grey")]),
             ("Online\n(every 500 ms)", 3.15, [("Live reading", "temperature, vibration, status, cycles", "blue"), ("Same features", "relative to the machine's own profile", "cyan"),
                                            ("Score the reading", "≤ 25 ms measured (limit 200 ms)", "violet"), ("Above 85 % for 2 readings?", "and below every hard limit", "yellow"),
                                            ("YELLOW caution", "operator gives true / false feedback", "orange")])]
    bw, bg = 1.55, 0.35
    for lab, y, items in lanes:
        box(s, X0, y, 1.3, 1.6, [{"text": t, "size": 14, "bold": True} for t in lab.split("\n")], fill="grey", edge="white")
        for i, (t, d, col) in enumerate(items):
            x = X0 + 1.5 + i * (bw + bg)
            box(s, x, y, bw, 1.6, [{"text": t, "size": 13, "bold": True, "space_after": 3}, {"text": d, "size": 12}], fill=col, edge=col, margin=0.07)
            if i < 4:
                line(s, x + bw + 0.02, y + 0.8, x + bw + bg - 0.02, y + 0.8, color=INK, w=2)
    for (x, w), (n, d) in zip(cols(4), [("6 / 6", "injected anomalies detected"), ("100 %", "precision on injected faults"),
                                       ("0", "false alarms per hour on healthy machines"), ("≤ 25 ms", "worst-case inference (limit 200 ms)")]):
        box(s, x, 5.0, w, 1.45, "", fill="green", edge="green")
        tb(s, x + 0.15, 5.08, w - 0.3, 0.65, n, size=30, bold=True, color=GREEN_D, anchor="m")
        tb(s, x + 0.15, 5.78, w - 0.3, 0.6, d, size=13)
    tb(s, X0, 6.55, W, 0.3, "If the ML service fails, the last score is kept and the Red rules keep working (NFR-R1).", size=13, color=MUTED, italic=True)

    # ================================================================== 21  What-If
    s = new("What-If Degradation & Projection (FR-07)",
            "The manager injects a controlled temperature rise over three minutes. The backend fits a straight line y = m x + c through the last three minutes of readings and predicts "
            "when the hard limit will be crossed. If that is within 60 seconds and the fit is good, the machine turns Orange with a countdown. The chart is an illustration with a slope of 0.1 degrees per second.")
    pts = [(t, 62 + 0.1 * (t + 180) + 0.7 * math.sin(t / 6.0)) for t in range(-180, 1, 10)]
    cd = XyChartData()
    s1 = cd.add_series("Temperature readings")
    for t, v in pts:
        s1.add_data_point(t, round(v, 2))
    s2 = cd.add_series("Fitted line  y = m·x + c")
    s2.add_data_point(-180, 62.0), s2.add_data_point(60, 86.0)
    s3 = cd.add_series("Hard limit 85 °C")
    s3.add_data_point(-180, 85), s3.add_data_point(60, 85)
    s4 = cd.add_series("Now")
    s4.add_data_point(0, 55), s4.add_data_point(0, 95)
    s5 = cd.add_series("Predicted crossing (ETA ≈ 50 s)")
    s5.add_data_point(50, 85)
    gf = s.shapes.add_chart(XL_CHART_TYPE.XY_SCATTER_LINES_NO_MARKERS, E(X0), E(1.1), E(6.6), E(4.95), cd)
    ch = gf.chart
    ch.font.size, ch.font.name = Pt(12), FONT
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.BOTTOM
    ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(11)
    sers = ch.plots[0].series
    sers[0].format.line.fill.background()
    sers[0].marker.style, sers[0].marker.size = XL_MARKER_STYLE.CIRCLE, 7
    sers[0].marker.format.fill.solid()
    sers[0].marker.format.fill.fore_color.rgb = EDGE["blue"]
    sers[0].marker.format.line.fill.background()
    for ser, colr, wd, dash in ((sers[1], EDGE["orange"], 2.5, False), (sers[2], EDGE["red"], 2.5, False), (sers[3], SLATE, 1.5, True)):
        ser.marker.style = XL_MARKER_STYLE.NONE
        ser.format.line.color.rgb = colr
        ser.format.line.width = Pt(wd)
        ser.smooth = False
        if dash:
            ser.format.line.dash_style = MSO_LINE.DASH
    sers[4].format.line.fill.background()
    sers[4].marker.style, sers[4].marker.size = XL_MARKER_STYLE.DIAMOND, 12
    sers[4].marker.format.fill.solid()
    sers[4].marker.format.fill.fore_color.rgb = EDGE["red"]
    xa, ya = ch.category_axis, ch.value_axis
    xa.crosses = XL_AXIS_CROSSES.MINIMUM
    ya.crosses = XL_AXIS_CROSSES.MINIMUM
    xa.minimum_scale, xa.maximum_scale, xa.major_unit = -180, 60, 30
    ya.minimum_scale, ya.maximum_scale, ya.major_unit = 55, 95, 5
    for ax, ttl in ((xa, "Time relative to now (s)"), (ya, "Temperature (°C)")):
        ax.has_title = True
        ax.axis_title.text_frame.text = ttl
        ax.axis_title.text_frame.paragraphs[0].runs[0].font.size = Pt(12)
        ax.axis_title.text_frame.paragraphs[0].runs[0].font.bold = False
        ax.tick_labels.font.size = Pt(12)
        if ax.has_major_gridlines:
            ax.major_gridlines.format.line.color.rgb = RGBColor(0xE2, 0xE8, 0xF0)
    tb(s, X0, 6.15, 6.6, 0.55, "Illustrative example: the line predicts the 85 °C limit in about 50 s (≤ 60 s), so the machine turns Orange.", size=13, color=MUTED, italic=True)
    rx0, rw0 = X0 + 6.85, W - 6.85
    st = ["Fit a straight line through the last **3 minutes** of temperature", "Compute **ETA = (limit − value now) ÷ slope**", "If ETA ≤ **60 s** and the fit is good (R² ≥ 0.6, slope ≥ 0.03 °C/s) → **ORANGE** + countdown",
          "If the limit is really crossed → **RED**"]
    for i, t in enumerate(st):
        y = 1.1 + i * 1.12
        box(s, rx0, y, rw0, 0.98, "", fill="orange", edge="orange")
        badge(s, rx0 + 0.42, y + 0.49, 0.46, str(i + 1), fill=EDGE["orange"])
        tb(s, rx0 + 0.85, y, rw0 - 1.0, 0.98, t, size=14, anchor="m")
    box(s, rx0, 5.7, rw0, 1.15, [{"text": "Measured in tests", "size": 14, "bold": True}, {"text": "Orange raised with ETA ≈ 28 s, then Red at 85.3 °C. Flat noise and short windows do not trigger it (unit-tested).", "size": 13}],
        fill="green", edge="green", align="l", margin=0.18)

    # ================================================================== 26  ER diagram
    s = new("Database Design – ER Diagram (PostgreSQL)",
            "Six tables. Machines own alerts and maintenance records; each alert can have one ML feedback row and several maintenance records. Users and ML model metadata are standalone. "
            "Time-series telemetry lives separately in InfluxDB (30 days raw, 1 year aggregated).")
    tw = 2.95
    tx = [X0, X0 + 4.0, X0 + 8.0]
    table_box(s, tx[0], 1.15, tw, "machines", [("id", "PK"), ("name", ""), ("kind", ""), ("ideal_cycle_s", ""), ("temp_limit", ""), ("vib_limit", "")], "blue")
    h_alerts = table_box(s, tx[1], 1.15, tw, "alerts", [("id", "PK"), ("machine_id", "FK"), ("level", ""), ("status", ""), ("opened_at", ""), ("acked_by", ""), ("technician", ""), ("resolution_notes", "")], "orange")
    table_box(s, tx[2], 1.15, tw, "feedback", [("id", "PK"), ("alert_id", "FK"), ("verdict", ""), ("given_by", ""), ("comment", "")], "violet")
    table_box(s, tx[2], 3.2, tw, "users", [("username", "PK"), ("role", ""), ("password_hash", "")], "grey")
    table_box(s, tx[2], 4.7, tw, "ml_models", [("id", "PK"), ("algorithm", ""), ("trained_at", ""), ("threshold", ""), ("metrics", "")], "yellow")
    table_box(s, tx[1], 4.3, tw, "maintenance_logs", [("id", "PK"), ("machine_id", "FK"), ("alert_id", "FK"), ("action", ""), ("technician", ""), ("status", "")], "green")
    line(s, tx[0] + tw, 2.0, tx[1], 2.0, color=INK, w=2, arrow=False)
    tb(s, tx[0] + tw, 1.68, 1.05, 0.26, "1 : N", size=12, bold=True, align="c")
    line(s, tx[1] + tw, 2.0, tx[2], 2.0, color=INK, w=2, arrow=False)
    tb(s, tx[1] + tw, 1.68, 1.05, 0.26, "1 : 1", size=12, bold=True, align="c")
    line(s, tx[1] + tw / 2, 1.15 + h_alerts, tx[1] + tw / 2, 4.3, color=INK, w=2, arrow=False)
    tb(s, tx[1] + tw / 2 + 0.1, 3.7, 0.8, 0.26, "1 : N", size=12, bold=True)
    path_pts = [(tx[0] + tw / 2, 1.15 + 1.9), (tx[0] + tw / 2, 4.9), (tx[1], 4.9)]
    for i in range(len(path_pts) - 1):
        line(s, *path_pts[i], *path_pts[i + 1], color=INK, w=2, arrow=False)
    tb(s, tx[0] + tw / 2 + 0.1, 3.9, 0.8, 0.26, "1 : N", size=12, bold=True)
    box(s, X0, 5.35, 3.4, 1.5, [{"text": "Time series (InfluxDB)", "size": 14, "bold": True}, {"text": "telemetry_raw – 30 days", "size": 13}, {"text": "telemetry_agg – 1 year", "size": 13}],
        fill="cyan", edge="cyan", align="l", margin=0.2)

    # ================================================================== 29  docker + requirements
    s = new("Deployment – Docker Compose & Requirements (SRS §10–11)",
            "One command starts the stack: Mosquitto, simulator, backend and the nginx-served React frontend. The two databases are an optional compose profile. "
            "The databases were verified live in Docker containers. The right panel is the hardware and software requirement table from the SRS.")
    box(s, X0, 1.1, 6.6, 0.55, "docker compose up --build", fill="grey", edge="grey", size=18, bold=True, color=INK)
    sv = cols(3, gap=0.375, x0=X0, w=6.6)
    names3 = [("simulator", "publishes telemetry", "blue"), ("mosquitto", ":1883 · :9001", "orange"), ("backend", ":8000 · /docs", "green")]
    for (x, w), (nm, d, col) in zip(sv, names3):
        box(s, x, 1.9, w, 1.1, [{"text": nm, "size": 15, "bold": True}, {"text": d, "size": 12}], fill=col, edge=col, margin=0.05)
    line(s, sv[0][0] + sv[0][1] + 0.01, 2.45, sv[1][0] - 0.01, 2.45, color=INK, w=2)
    line(s, sv[1][0] + sv[1][1] + 0.01, 2.45, sv[2][0] - 0.01, 2.45, color=INK, w=2)
    box(s, sv[2][0], 3.75, sv[2][1], 1.1, [{"text": "frontend", "size": 15, "bold": True}, {"text": "nginx · :5173", "size": 12}], fill="cyan", edge="cyan", margin=0.05)
    line(s, sv[2][0] + 1.0, 3.74, sv[2][0] + 1.0, 3.01, color=INK, w=2, back_arrow=True)
    box(s, X0, 3.75, 4.35, 1.1, "", fill=None, edge="grey", dash=True, radius=0.1)
    tb(s, X0 + 0.15, 3.8, 4.1, 0.3, "optional profile  --profile db", size=12, color=MUTED, italic=True)
    for k, (nm, d) in enumerate([("PostgreSQL 14", ":5432"), ("InfluxDB 2", ":8086")]):
        box(s, X0 + 0.15 + k * 2.1, 4.15, 1.95, 0.6, [{"text": nm, "size": 13, "bold": True}, {"text": d, "size": 11}], fill="violet", edge="violet", margin=0.03)
    path(s, [(sv[2][0] + 0.3, 3.01), (sv[2][0] + 0.3, 3.4), (X0 + 2.18, 3.4), (X0 + 2.18, 3.74)], color=INK, w=2)
    card(s, X0, 5.15, 6.6, 1.7, "green", "Verified live", ["PostgreSQL 14 and InfluxDB 2 running in Docker: telemetry, alerts, acknowledgements, feedback and maintenance saved and still there after a backend restart"], size=14, bullets=False)
    rxx, rww = X0 + 6.85, W - 6.85
    box(s, rxx, 1.1, rww, 5.75, "", fill="grey", edge="white")
    tb(s, rxx + 0.2, 1.22, rww - 0.4, 0.4, "Requirements (SRS §11)", size=17, bold=True)
    tb(s, rxx + 0.2, 1.75, rww - 0.4, 2.0, [{"text": "Hardware – minimum → recommended", "size": 14, "bold": True, "space_after": 4},
                                           {"text": "CPU: dual-core 2.0 GHz → quad-core 2.5 GHz", "size": 13, "bullet": True, "space_after": 3},
                                           {"text": "RAM: 8 GB → 16 GB", "size": 13, "bullet": True, "space_after": 3},
                                           {"text": "Storage: 20 GB free → 50 GB SSD", "size": 13, "bullet": True, "space_after": 3},
                                           {"text": "Display: 1366 × 768 → 1920 × 1080", "size": 13, "bullet": True}], size=13)
    tb(s, rxx + 0.2, 3.85, rww - 0.4, 2.9, [{"text": "Software", "size": 14, "bold": True, "space_after": 4},
                                           {"text": "Windows 10/11, Ubuntu 20.04+, macOS 11+", "size": 13, "bullet": True, "space_after": 3},
                                           {"text": "Docker Desktop 4.x + Compose 2.x", "size": 13, "bullet": True, "space_after": 3},
                                           {"text": "Python 3.10+ and Node 18+ (containerised)", "size": 13, "bullet": True, "space_after": 3},
                                           {"text": "PostgreSQL 14, InfluxDB 2, Mosquitto 2", "size": 13, "bullet": True, "space_after": 3},
                                           {"text": "Chrome, Firefox or Edge", "size": 13, "bullet": True}], size=13)
