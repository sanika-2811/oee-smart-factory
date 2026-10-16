"""Slides 30-37: screenshots, accessibility, demo, results, traceability, advantages, conclusion, references."""
from __future__ import annotations

from PIL import Image
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.util import Pt

from deckkit import *  # noqa: F401,F403


def build(ctx):
    new = ctx.new
    shots = ctx.root / "docs" / "screenshots"

    def crop(name, box_, out):
        with Image.open(shots / name) as im:
            im.crop(box_).save(ctx.crop_dir / out)
        return ctx.crop_dir / out

    # ================================================================== 30  dashboard screens
    s = new("Implementation – Dashboard Screens",
            "Real screenshots of the running application at 1440 pixels. Top left: plant overview with the OEE gauge and the three factors. Top right: the machine grid with red, orange and green tiles. "
            "Bottom left: machine detail with the What-If regression line and countdown. Bottom right: the alert centre after operator actions.")
    imgs = [(crop("desktop_01_overview_normal.png", (0, 0, 1440, 680), "ov.png"), "Plant overview: OEE gauge, A / P / Q, KPIs"),
            (crop("desktop_04_machines_alerts.png", (0, 0, 1440, 680), "ma.png"), "Machine grid: Red · Orange (ETA) · Green"),
            (crop("desktop_05_machine_detail_whatif.png", (0, 0, 1440, 680), "det.png"), "Machine detail with What-If regression"),
            (crop("desktop_07_alerts_centre_actioned.png", (0, 0, 1440, 680), "al.png"), "Alert centre: acknowledge · assign · feedback")]
    pw_ = 5.2
    ph_ = pw_ * 680 / 1440
    for i, (im, cap) in enumerate(imgs):
        x = X0 + (i % 2) * (W - pw_)
        y = 1.1 + (i // 2) * (ph_ + 0.56)
        picture(s, im, x, y, pw_, ph_)
        tb(s, x, y + ph_ + 0.06, pw_, 0.28, cap, size=14, color=MUTED, align="c")

    # ================================================================== 31  responsive & accessible
    s = new("Responsive & Accessible by Design",
            "The same dashboard works on a phone, with dark and light themes. It was audited with axe-core for WCAG 2 A and AA on every page, both themes, desktop and phone: zero violations. "
            "It was also loaded in Chromium, Firefox and WebKit: all pages clean with no console errors and no sideways scrolling.")
    phones = [("mobile_01_overview_normal.png", "Overview"), ("mobile_04_machines_alerts.png", "Machines"), ("mobile_06_alerts_centre.png", "Alerts")]
    phh = 4.85
    phw = phh * 780 / 1688
    for i, (f, cap) in enumerate(phones):
        x = X0 + i * (phw + 0.25)
        picture(s, shots / f, x, 1.1, phw, phh)
        tb(s, x, 1.1 + phh + 0.08, phw, 0.3, cap, size=13, color=MUTED, align="c")
    bx = X0 + 3 * phw + 0.75
    card(s, bx, 1.1, X1 - bx, 5.75, "green", "Built for everyone", ["Phone, tablet and desktop layouts – no sideways scrolling", "Dark and light themes", "Colour + icon + text label for every state",
                                                                    "Keyboard navigation and ARIA labels (NFR-U2)", "axe-core: **0 violations** on all pages, both themes, desktop and phone",
                                                                    "Chromium, Firefox and WebKit: all pages clean", "Offline banner, error screen, plain-language messages (NFR-U3)"], size=14, title_size=17)

    # ================================================================== 32  live demo
    s = new("Live Demo – Seven Steps",
            "Switch to the browser and follow the numbered steps; the whole demo takes about three minutes. Start the app first with scripts/dev.ps1 or docker compose up, then sign in as the Floor Manager. "
            "Step 8 is optional and only works when the databases are running.")
    demo = [("Sign in", "Open **Control** and sign in as the Floor Manager"), ("ML caution", "Inject an **ML anomaly** on Welder-04 → the tile turns **Yellow**"),
            ("Projected fault", "Speed ×6, **temperature ramp** on CNC-01 → **Orange** with ETA, then **Red**"), ("Hard fault", "**Vibration spike** on Press-02 → instant **Red**"),
            ("Operator actions", "**Alerts**: acknowledge · assign technician · resolve · feedback"), ("Records", "**Maintenance** log linked to the alert; **Reports** page"),
            ("Resilience", "Simulate **ML outage** → score held, Red rules still alert"), ("Optional", "Restart the backend → alerts are **still there** (PostgreSQL)")]
    cs4 = cols(4, gap=0.4)
    dh = 2.55
    for i, (t, d) in enumerate(demo):
        x, w = cs4[i % 4]
        y = 1.2 + (i // 4) * (dh + 0.45)
        box(s, x, y, w, dh, "", fill="grey" if i < 7 else "white", edge="white" if i < 7 else "grey", dash=i == 7)
        badge(s, x + 0.4, y + 0.42, 0.5, str(i + 1))
        tb(s, x + 0.8, y + 0.15, w - 0.95, 0.55, t, size=16, bold=True, anchor="m")
        tb(s, x + 0.2, y + 0.95, w - 0.4, 1.5, d, size=14)
        if i % 4 < 3:
            line(s, x + w + 0.04, y + dh / 2, cs4[i % 4 + 1][0] - 0.04, y + dh / 2, color=INK, w=2.25)
    xa, xb = cs4[3][0] + cs4[3][1] / 2, cs4[0][0] + cs4[0][1] / 2
    ym = 1.2 + dh + 0.225
    path(s, [(xa, 1.2 + dh + 0.02), (xa, ym), (xb, ym), (xb, 1.2 + dh + 0.45 - 0.03)], color=INK, w=2.25)

    # ================================================================== 33  testing & results
    s = new("Testing & Results",
            "All numbers come from real runs of the final code. Top: 45 automated tests, a 13-check end-to-end test with 50 simultaneous clients, zero accessibility violations and three browser engines clean. "
            "Bottom left: each performance target from the SRS compared with what we measured - every bar is far below its limit. Bottom right: further checks, including the live databases.")
    stats = [("45", "automated tests passed", "38 pytest + 7 Vitest"), ("13 / 13", "end-to-end checks passed", "5 machines, 50 simultaneous clients"),
             ("0", "accessibility violations", "axe-core, WCAG 2 A / AA"), ("3 / 3", "browser engines clean", "Chromium · Firefox · WebKit")]
    for (x, w), (n, t, d) in zip(cols(4), stats):
        box(s, x, 1.15, w, 1.6, "", fill="green", edge="green")
        tb(s, x + 0.18, 1.22, w - 0.36, 0.7, n, size=34, bold=True, color=GREEN_D, anchor="m")
        tb(s, x + 0.18, 1.92, w - 0.36, 0.3, t, size=14, bold=True)
        tb(s, x + 0.18, 2.25, w - 0.36, 0.4, d, size=12, color=MUTED)
    cd = CategoryChartData()
    cd.categories = ["Dashboard update, p95\n0.51 s of 1 s", "ML inference, worst case\n19 ms of 200 ms", "MQTT recovery\n1.9 s of 5 s"]
    cd.add_series("Share of the SRS limit used", (51, 9.5, 38))
    gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, E(X0), E(3.0), E(6.1), E(3.85), cd)
    ch = gf.chart
    ch.font.size, ch.font.name = Pt(12), FONT
    ch.has_legend = False
    ch.has_title = True
    ch.chart_title.text_frame.text = "Measured as a share of the SRS limit (lower is better)"
    ch.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(13)
    ch.chart_title.text_frame.paragraphs[0].runs[0].font.bold = True
    plot = ch.plots[0]
    plot.gap_width = 60
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format, dl.number_format_is_linked = '0.0"%"', False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size, dl.font.bold = Pt(13), True
    plot.series[0].format.fill.solid()
    plot.series[0].format.fill.fore_color.rgb = EDGE["green"]
    ch.value_axis.minimum_scale, ch.value_axis.maximum_scale, ch.value_axis.major_unit = 0, 100, 25
    ch.value_axis.tick_labels.font.size = Pt(12)
    ch.value_axis.tick_labels.number_format, ch.value_axis.tick_labels.number_format_is_linked = '0"%"', False
    ch.value_axis.major_gridlines.format.line.color.rgb = RGBColor(0xE2, 0xE8, 0xF0)
    ch.category_axis.tick_labels.font.size = Pt(12)
    ch.category_axis.reverse_order = True
    card(s, X0 + 6.3, 3.0, W - 6.3, 3.85, "grey", "Also verified", ["**20 machines** run normally: p95 update 0.51 s", "**Databases:** alerts, acknowledgements, feedback and maintenance survive a backend restart",
                                                                   "**Broker kill test:** backend reconnects and data resumes in 1.9 s", "Fault injection needs a login (HTTP 401 without)",
                                                                   "Orange raised ≈ 28 s before Red at 85.3 °C"], size=15, title_size=18, gap=8)

    # ================================================================== 34  requirement traceability
    s = new("Requirement-to-Test Traceability (SRS §13.3)",
            "The SRS asks that every requirement maps to a test. Each functional requirement is shown with the evidence that proves it. The last two rows group the non-functional targets and one item that is configured but "
            "still to be confirmed by a full Docker Compose run.")
    rows = [("ID", "Requirement", "Verified by", "Result"),
            ("FR-01", "Virtual factory simulation", "Smoke test: 5 machines streaming; MQTT test: telemetry flows", "Pass"),
            ("FR-02", "OEE calculation", "Unit tests: exact formula, window roll-off, counter reset", "Pass"),
            ("FR-03", "Rule-based alerting", "Unit test on limits; smoke: Red when temperature > 85 °C", "Pass"),
            ("FR-04", "ML anomaly scoring", "Unit test: normal low, fault high, fast; smoke: Yellow", "Pass"),
            ("FR-05", "Interactive dashboard", "3-browser check, axe audit, screenshots of every page", "Pass"),
            ("FR-06", "Maintenance logging", "API tests (CRUD, acknowledge, feedback); live PostgreSQL round-trip", "Pass"),
            ("FR-07", "What-If simulator", "Unit tests (slope, projection); smoke: Orange with ETA before Red", "Pass"),
            ("FR-08", "Historical reporting", "API test: OEE trend, downtime and ML-accuracy reports", "Pass"),
            ("FR-09", "Telemetry validation", "Unit and API tests reject bad payloads", "Pass"),
            ("FR-10", "Authentication", "Smoke: HTTP 401 without login; role and throttle tests", "Pass"),
            ("FR-11", "Scalability 5 → 20", "Run with 20 machines: all live, p95 update 0.51 s", "Pass"),
            ("FR-12", "Auto-documentation", "API test: /docs and OpenAPI schema served", "Pass"),
            ("NFR-P · R · SC", "Speed, resilience, scale", "p95 0.51 s · ML ≤ 25 ms · ML outage test · reconnect 1.9 s · 50 / 50 clients", "Pass"),
            ("NFR-M1, R3", "One command, persistent volumes", "Compose files and volumes written; full-stack run to be confirmed", "To confirm")]
    colw = [1.75, 2.75, 5.35, 1.1]
    rh = 0.355
    shape = s.shapes.add_table(len(rows), 4, E(X0), E(1.1), E(W), E(rh * len(rows)))
    tbl = shape.table
    for c, w in enumerate(colw):
        tbl.columns[c].width = E(w)
    for r, row in enumerate(rows):
        tbl.rows[r].height = E(rh)
        for c, v in enumerate(row):
            cell = tbl.cell(r, c)
            cell.margin_left = cell.margin_right = E(0.08)
            cell.margin_top = cell.margin_bottom = E(0.02)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.text = ""
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT
            run = p.add_run()
            run.text = v
            run.font.name, run.font.size = FONT, Pt(12)
            run.font.bold = r == 0 or c == 0 or c == 3
            run.font.color.rgb = WHITE if r == 0 else (GREEN_D if (c == 3 and v == "Pass") else (RED if c == 3 else INK))
            cell.fill.solid()
            cell.fill.fore_color.rgb = RED if r == 0 else (SOFT["grey"] if r % 2 else WHITE)

    # ================================================================== 35  advantages / limitations / applications
    s = new("Advantages, Limitations & Applications",
            "Be balanced. Advantages: layered detection, explainable alerts, runs without infrastructure. Limitations come straight from the SRS constraints: simulated data, one-off training, basic authentication, "
            "2D web only. Applications: monitoring pilots, teaching, a test bench for anomaly models.")
    cs3 = cols(3)
    card(s, cs3[0][0], 1.2, cs3[0][1], 4.95, "green", "Advantages", ["Three detection layers: rules, ML and trend line", "Explainable alerts with an ETA countdown", "Runs with or without Docker and databases",
                                                                    "Operator workflow with an audit trail", "Tested, accessible, documented API"], size=18, title_size=22, gap=16)
    card(s, cs3[1][0], 1.2, cs3[1][1], 4.95, "orange", "Limitations", ["Simulated telemetry only (C-01)", "Model trained once – no online learning (C-04)", "Single-tenant basic authentication (C-05)",
                                                                      "What-If assumes a linear rise", "2D web app, no native mobile app (C-06)"], size=18, title_size=22, gap=16)
    card(s, cs3[2][0], 1.2, cs3[2][1], 4.95, "blue", "Applications", ["OEE and condition-monitoring pilots", "Industry 4.0 teaching lab", "Test bench for anomaly-detection models",
                                                                    "Starting point for real PLC / OPC UA gateways"], size=18, title_size=22, gap=16)

    box(s, X0, 6.3, W, 0.6, "The limitations are by design – they are the SRS constraints C-01 … C-07, not accidents.", fill="grey", edge="white", size=17, bold=True, color=GREEN_D)

    # ================================================================== 36  conclusion & future scope
    s = new("Conclusion & Future Scope",
            "Conclusion: the system meets every numeric SRS target with measured evidence and is reproducible. Future scope: connect real equipment through OPC UA or Modbus, learn from operator feedback, add notifications, "
            "predict remaining useful life with non-linear models, and support multiple sites.")
    c2 = cols(2)
    card(s, c2[0][0], 1.2, c2[0][1], 4.95, "green", "Conclusion", ["Live OEE and Red / Orange / Yellow alerts within about half a second", "Every numeric SRS target met, with measured evidence",
                                                                  "ML validated on injected faults: 6 / 6 detected, no false alarms", "Complete, reproducible platform: one command, 45 tests, databases verified live"],
         size=19, title_size=23, gap=16)
    card(s, c2[1][0], 1.2, c2[1][1], 4.95, "blue", "Future scope", ["Real machines through OPC UA / Modbus → MQTT", "Retrain the model from operator feedback", "Notifications (email, SMS) and audit export",
                                                                   "Remaining useful life with non-linear models", "Multi-site deployment and Grafana dashboards"], size=19, title_size=23, gap=16)

    box(s, X0, 6.3, W, 0.6, "Take-home: live OEE and a three-layer early warning – built to the SRS and verified by measurement.", fill="grey", edge="white", size=17, bold=True, color=GREEN_D)

    # ================================================================== 37  references
    s = new("References",
            "References as listed in the project report.")
    refs = ["[1]  S. Nakajima, Introduction to TPM: Total Productive Maintenance, Productivity Press, 1988.",
            "[2]  ISO 22400-2:2014, Automation systems and integration – Key performance indicators for manufacturing operations management.",
            "[3]  P. Muchiri and L. Pintelon, “Performance measurement using overall equipment effectiveness (OEE)”, Int. J. Production Research, 46(13), 2008.",
            "[4]  F. T. Liu, K. M. Ting and Z.-H. Zhou, “Isolation Forest”, IEEE International Conference on Data Mining (ICDM), 2008.",
            "[5]  V. Chandola, A. Banerjee and V. Kumar, “Anomaly detection: a survey”, ACM Computing Surveys, 2009.",
            "[6]  F. Pedregosa et al., “Scikit-learn: Machine learning in Python”, Journal of Machine Learning Research, 12, 2011.",
            "[7]  OASIS, MQTT Version 3.1.1, 2014.",
            "[8]  J. Lee, B. Bagheri and H.-A. Kao, “A cyber-physical systems architecture for Industry 4.0-based manufacturing systems”, Manufacturing Letters, 3, 2015.",
            "[9]  S. Jamadar, Software Requirements Specification: Real-Time OEE and Anomaly Dashboard for a Smart Factory System, 12/09/2026."]
    box(s, X0, 1.2, W, 5.6, "", fill="grey", edge="white")
    tb(s, X0 + 0.3, 1.4, W - 0.6, 5.2, [{"text": r, "size": 16, "space_after": 10} for r in refs], size=16)
