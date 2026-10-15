"""Build the 16-slide project presentation on the NMIMS template (docs/templates/Presentation_Format.pptx).

    python presentation/build_pptx.py      # -> presentation/OEE_Smart_Factory_Presentation.pptx
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "docs" / "templates" / "Presentation_Format.pptx"
OUT = ROOT / "presentation" / "OEE_Smart_Factory_Presentation.pptx"
FIG = ROOT / "report" / "figures"
SHOT = ROOT / "docs" / "screenshots"
CROP = ROOT / "presentation" / "_crops"
CROP.mkdir(exist_ok=True)

FONT = "Times New Roman"
INK = RGBColor(0x11, 0x18, 0x27)
MUTED = RGBColor(0x47, 0x55, 0x69)
RED = RGBColor(0xC0, 0x00, 0x00)
GREEN_D = RGBColor(0x37, 0x56, 0x23)
LV = {"green": RGBColor(0x22, 0xC5, 0x5E), "yellow": RGBColor(0xFA, 0xCC, 0x15), "orange": RGBColor(0xFB, 0x92, 0x3C), "red": RGBColor(0xEF, 0x44, 0x44)}
SOFT = {"green": RGBColor(0xDC, 0xFC, 0xE7), "yellow": RGBColor(0xFE, 0xF9, 0xC3), "orange": RGBColor(0xFF, 0xED, 0xD5), "red": RGBColor(0xFE, 0xE2, 0xE2),
        "blue": RGBColor(0xDB, 0xEA, 0xFE), "grey": RGBColor(0xF1, 0xF5, 0xF9), "violet": RGBColor(0xED, 0xE9, 0xFE)}

prs = Presentation(str(TEMPLATE))
LAYOUT = prs.slide_layouts.get_by_name("Title and Content")
LEFT = Inches(1.95)          # content starts right of the logo tab
RIGHT_EDGE = Inches(12.9)


def clear_placeholders(slide):
    for sh in list(slide.placeholders):
        if sh.placeholder_format.type is not None and "SLIDE_NUMBER" not in str(sh.placeholder_format.type):
            sh._element.getparent().remove(sh._element)


def text(slide, x, y, w, h, content, size=18, bold=False, color=INK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, italic=False):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05)
    lines = content if isinstance(content, list) else [content]
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        parts = ln.split("**")
        for k, part in enumerate(parts):
            if part:
                r = p.add_run()
                r.text = part
                r.font.name, r.font.size, r.font.bold, r.font.italic = FONT, Pt(size), bold or k % 2 == 1, italic
                r.font.color.rgb = color
    return tb


def bullet_list(slide, x, y, w, h, items, size=18, gap=6, color=INK):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        parts = ("•  " + it).split("**")
        for k, part in enumerate(parts):
            if part:
                r = p.add_run()
                r.text = part
                r.font.name, r.font.size, r.font.bold = FONT, Pt(size), k % 2 == 1
                r.font.color.rgb = color
    return tb


def card(slide, x, y, w, h, fill, title=None, body=None, edge=None, size=14, title_size=16):
    sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    sh.adjustments[0] = 0.08
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    sh.line.color.rgb = edge or RGBColor(0xCB, 0xD5, 0xE1)
    sh.line.width = Pt(1.5)
    sh.shadow.inherit = False
    tf = sh.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_left = tf.margin_right = Inches(0.12)
    tf.margin_top = Inches(0.08)
    first = True
    if title:
        p = tf.paragraphs[0]
        r = p.add_run()
        r.text = title
        r.font.name, r.font.size, r.font.bold = FONT, Pt(title_size), True
        r.font.color.rgb = INK
        first = False
    for ln in (body if isinstance(body, list) else [body] if body else []):
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_before = Pt(2)
        for k, part in enumerate(ln.split("**")):
            if part:
                r = p.add_run()
                r.text = part
                r.font.name, r.font.size, r.font.bold = FONT, Pt(size), k % 2 == 1
                r.font.color.rgb = INK
    return sh


def picture(slide, path, x, y, w=None, h=None):
    with Image.open(path) as im:
        iw, ih = im.size
    if w is not None and h is not None:
        scale = min(w / iw, h / ih)
        pw, ph = int(iw * scale), int(ih * scale)
        x, y = x + (w - pw) // 2, y + (h - ph) // 2
        pic = slide.shapes.add_picture(str(path), x, y, pw, ph)
    else:
        pic = slide.shapes.add_picture(str(path), x, y, w, h)
    pic.line.color.rgb = RGBColor(0xCB, 0xD5, 0xE1)
    pic.line.width = Pt(1)
    return pic


def new_slide(title, notes):
    s = prs.slides.add_slide(LAYOUT)
    clear_placeholders(s)
    text(s, LEFT, Inches(0.1), Inches(10.8), Inches(0.55), title, size=28, bold=True, color=RGBColor(255, 255, 255), anchor=MSO_ANCHOR.MIDDLE)
    s.notes_slide.notes_text_frame.text = notes
    return s


def crop(name, box, out):
    with Image.open(SHOT / name) as im:
        im.crop(box).save(CROP / out)
    return CROP / out


# ======================================================================== slide 1 (template title)
s1 = prs.slides[0]
for sh in s1.shapes:
    if sh.has_text_frame and "TITLE OF PROJECT" in sh.text_frame.text:
        tf = sh.text_frame
        lines = ["A Presentation on", "“AI-Enhanced Real-Time OEE and Anomaly Dashboard", "for a Smart Factory System”", "",
                 "By", "Sanika Jamadar  (Roll No. B291, Batch A2)", "", "Under the Guidance of", "Dr. Naziya Hussain"]
        for i, p in enumerate(list(tf.paragraphs)):
            if i > 0:
                p._p.getparent().remove(p._p)
        first = tf.paragraphs[0]
        for r in list(first.runs):
            r._r.getparent().remove(r._r)
        for i, ln in enumerate(lines):
            p = first if i == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.CENTER
            r = p.add_run()
            r.text = ln
            r.font.name, r.font.bold = FONT, True
            r.font.size = Pt(26 if i in (1, 2) else 22)
            r.font.color.rgb = INK
s1.notes_slide.notes_text_frame.text = ("Introduce yourself and the project. One sentence: a software-only smart-factory monitor that shows OEE live and "
                                        "warns operators three different ways - rules, a machine-learning model and a trend projection - before a machine fails.")

# ======================================================================== slide 2 agenda (template) - keep, add notes
prs.slides[1].notes_slide.notes_text_frame.text = "Quick roadmap. The talk is about 10 minutes plus a live demo; screenshots are real captures of the running app."

# ======================================================================== 3 Introduction & problem
s = new_slide("Introduction & Problem Statement",
              "OEE is the standard productivity KPI: Availability x Performance x Quality. Today it is often computed after the shift, and alarms fire only at fixed "
              "limits. Operators need one live view that warns early. State the four needs on the right and the numeric targets from the SRS at the bottom.")
card(s, LEFT, Inches(1.2), Inches(5.3), Inches(4.3), SOFT["blue"], "Background", [
    "• Industry 4.0: machines are instrumented and connected",
    "• **OEE = Availability × Performance × Quality** is the standard productivity KPI (ISO 22400)",
    "• Fixed alarm limits fire late; predictive maintenance needs earlier warning",
    "• Real plants are rarely available to students → a **virtual factory** makes everything demonstrable",
], size=16)
card(s, Inches(7.45), Inches(1.2), Inches(5.45), Inches(4.3), SOFT["orange"], "Problem statement", [
    "Managers and engineers lack one live view that:",
    "1. shows **OEE** per machine and plant-wide",
    "2. flags **hard faults** instantly",
    "3. detects **subtle anomalies** limits miss",
    "4. **predicts** a breach early enough to act",
], size=16)
text(s, LEFT, Inches(5.75), Inches(10.9), Inches(1.0),
     ["SRS targets: updates ≤ 1 s · ML inference ≤ 200 ms · MQTT reconnect ≤ 5 s · 50 concurrent clients · 5 → 20 machines"], size=16, bold=True, color=GREEN_D)

# ======================================================================== 4 Objectives
s = new_slide("Objectives", "Read the six objectives; each maps to a requirement in the SRS (FR-01 to FR-12). Emphasise that everything is verified by tests, not just claimed.")
objs = [("1", "Simulate", "5–20 virtual machines, 500 ms telemetry, injectable faults"), ("2", "Measure", "Rolling 1 h / 8 h OEE per machine and plant"),
        ("3", "Detect", "Rule (Red), ML Isolation Forest (Yellow), What-If trend (Orange)"), ("4", "Act", "Acknowledge, assign, resolve, feedback, maintenance log"),
        ("5", "Report", "7-day OEE trend, downtime per shift, ML accuracy"), ("6", "Run anywhere", "One command; works with or without Docker and databases")]
for i, (n, t, d) in enumerate(objs):
    x = LEFT + (i % 2) * Inches(5.5)
    y = Inches(1.25) + (i // 2) * Inches(1.8)
    card(s, x, y, Inches(5.3), Inches(1.6), SOFT["grey"], f"{n}.  {t}", [d], size=15, title_size=19)

# ======================================================================== 5 Existing vs proposed
s = new_slide("Existing vs. Proposed System", "Contrast: today OEE is retrospective and alarms are fixed thresholds. Our system is live, layered and explainable, and it runs with no hardware.")
rows = [("", "Existing practice", "Proposed system"), ("OEE", "Spreadsheets after the shift", "Live 1 h / 8 h, A × P × Q shown separately"),
        ("Fault detection", "Fixed alarm limits only", "Rules + Isolation Forest + What-If projection"),
        ("Warning time", "None – alarm at breach", "Orange up to 60 s ahead with ETA"),
        ("Operator workflow", "Paper / chat", "Ack, assign, resolve, feedback, maintenance log"),
        ("Deployment", "Vendor systems, hardware needed", "Open software, one command, no hardware")]
tbl = s.shapes.add_table(len(rows), 3, LEFT, Inches(1.3), Inches(10.9), Inches(4.4)).table
for c, w in enumerate((2.4, 3.9, 4.6)):
    tbl.columns[c].width = Inches(w)
for r, row in enumerate(rows):
    for c, v in enumerate(row):
        cell = tbl.cell(r, c)
        cell.text = ""
        p = cell.text_frame.paragraphs[0]
        run = p.add_run()
        run.text = v
        run.font.name, run.font.size, run.font.bold = FONT, Pt(16), r == 0 or c == 0
        run.font.color.rgb = RGBColor(255, 255, 255) if r == 0 else INK
        cell.fill.solid()
        cell.fill.fore_color.rgb = RED if r == 0 else (SOFT["green"] if c == 2 else SOFT["grey"])

# ======================================================================== 6 Architecture
s = new_slide("System Architecture", "Walk left to right: the simulator publishes JSON over MQTT (WebSockets) to Mosquitto; the FastAPI backend validates, computes OEE, runs the three "
                                     "detectors, stores data and pushes a snapshot every 500 ms to the React dashboard. Storage is a switch: memory by default, InfluxDB + PostgreSQL when configured.")
picture(s, FIG / "architecture.png", LEFT, Inches(1.0), Inches(10.9), Inches(5.9))

# ======================================================================== 7 Tech stack
s = new_slide("Technology Stack", "Name the tools; each was chosen from the SRS. Highlight that the frontend and backend are fully typed and tested.")
stack = [("Simulator", "Python 3 · paho-mqtt", "blue"), ("Messaging", "Eclipse Mosquitto · MQTT over WebSockets", "orange"), ("Backend", "FastAPI · Pydantic v2 · asyncio", "green"),
         ("Machine learning", "scikit-learn Isolation Forest · NumPy", "yellow"), ("Time series", "InfluxDB v2 (30 d raw / 1 y aggregated)", "blue"),
         ("Relational", "PostgreSQL 14 · SQLAlchemy", "violet"), ("Frontend", "React 18 · TypeScript · Vite · Chart.js", "green"), ("Deployment", "Docker Compose · nginx", "grey"),
         ("Quality", "pytest · Vitest · Playwright", "red")]
for i, (t, d, col) in enumerate(stack):
    x = LEFT + (i % 3) * Inches(3.68)
    y = Inches(1.3) + (i // 3) * Inches(1.9)
    card(s, x, y, Inches(3.5), Inches(1.7), SOFT[col], t, [d], size=15, title_size=19)

# ======================================================================== 8 Alert logic
s = new_slide("Alert Logic – Four Colours", "This is the heart of the system. Red is certain and immediate. Orange uses a regression line to predict a crossing within 60 seconds. Yellow comes from the "
                                            "Isolation Forest when the score passes 85 percent. Higher levels suppress lower ones. Every colour also has an icon and a label for accessibility.")
cards = [("green", "GREEN  ✓  Normal", ["Operating normally", "No active condition"]),
         ("yellow", "YELLOW  ▲  ML caution", ["Isolation Forest anomaly score **> 85 %**", "2 consecutive ticks; below every hard limit"]),
         ("orange", "ORANGE  ↗  Projected fault", ["Line **y = m·x + c** through last 3 min", "Crossing within **60 s** → ETA countdown"]),
         ("red", "RED  ✕  Hard fault", ["Temperature or vibration **> limit**", "or machine STOPPED – immediate"])]
for i, (lv, t, body) in enumerate(cards):
    card(s, LEFT + (i % 2) * Inches(5.5), Inches(1.25) + (i // 2) * Inches(2.45), Inches(5.3), Inches(2.25), SOFT[lv], t, body, edge=LV[lv], size=20, title_size=24)
text(s, LEFT, Inches(6.3), Inches(10.9), Inches(0.5), "Priority: Red > Orange > Yellow > Green · open after 1–2 ticks · clear after 3–4 s · operator can acknowledge, assign, resolve, give feedback", size=14, color=MUTED, italic=True)

# ======================================================================== 9 OEE
s = new_slide("OEE – Availability × Performance × Quality", "Explain the three factors with the formula; then show the live plant numbers from the test run. Rolling windows are O(1) running sums so it scales to 20 machines.")
card(s, LEFT, Inches(1.25), Inches(5.4), Inches(4.0), SOFT["blue"], "Definition", [
    "**Availability** = run time ÷ planned time", "**Performance** = (cycles × ideal cycle time) ÷ run time", "**Quality** = good cycles ÷ total cycles",
    "**OEE = A × P × Q**", "", "Rolling **1 h** and **8 h** windows (5-second buckets, O(1) reads); plant OEE from summed components"], size=16, title_size=19)
card(s, Inches(7.55), Inches(1.25), Inches(5.35), Inches(4.0), SOFT["green"], "Measured in the end-to-end test (1 h)", [
    "Availability  **97.4 %**", "Performance  **88.1 %**", "Quality  **98.1 %**", "**OEE  84.2 %**   (8 h window: 83.7 %)", "",
    "5 machines · 7 days of simulated history back-fill"], size=17, title_size=19)
text(s, LEFT, Inches(5.6), Inches(10.9), Inches(0.9), "Dashboard shows the three rings next to the final figure so the cause of a loss is visible at a glance.", size=16, color=MUTED, italic=True)

# ======================================================================== 10 ML + What-If
s = new_slide("ML Anomaly Scoring & What-If Projection", "Left: one Isolation Forest for all machines using per-machine normalised features, calibrated to a 0-100 percent score. We validated it on injected faults: "
                                                         "six of six detected, 100 percent precision, no false alarms. Right: a least squares line over three minutes predicts when the limit will be hit.")
card(s, LEFT, Inches(1.2), Inches(5.4), Inches(5.2), SOFT["yellow"], "Isolation Forest (pre-trained)", [
    "• Trained on **synthetic normal** data (68 687 rows, 20 machine profiles); trimmed tail",
    "• 6 normalised features: level, dynamics, joint magnitudes",
    "• Score calibrated to **0–100 %**; threshold 85 %",
    "• Inference **≤ 36 ms** (target 200 ms)",
    "• Validation on injected faults: **6/6 detected, precision 100 %, 0 false alarms/h**",
    "• ML outage → last score held, Red rules keep working"], size=15, title_size=18)
card(s, Inches(7.55), Inches(1.2), Inches(5.35), Inches(5.2), SOFT["orange"], "What-If projection  y = m·x + c", [
    "• Least-squares line through the last **3 min** of temperature",
    "• ETA = (limit − fit_now) ÷ m",
    "• **Orange** when ETA ≤ **60 s** (R² ≥ 0.6, slope ≥ 0.03 °C/s)",
    "• Dashboard draws points, fitted line, limit and countdown",
    "• Manual scenario: controlled 3-minute temperature rise (demo speed up to ×6)",
    "• Measured: Orange raised with ETA 25 s, then Red at 85.1 °C"], size=15, title_size=18)

# ======================================================================== 11 UI screenshots
s = new_slide("Implementation – Dashboard Screens", "Real screenshots from the running application at 1440 pixels. Top left overview, top right machine grid with red orange and green, bottom left the machine detail with the "
                                                    "regression line, bottom right the alert centre after operator actions.")
imgs = [crop("desktop_01_overview_normal.png", (0, 0, 1440, 900), "ov.png"), SHOT / "desktop_04_machines_alerts.png",
        crop("desktop_05_machine_detail_whatif.png", (0, 0, 1440, 1160), "det.png"), crop("desktop_07_alerts_centre_actioned.png", (0, 0, 1440, 900), "al.png")]
caps = ["Plant overview: OEE gauge, A/P/Q, KPIs", "Machine grid: Red · Orange (ETA) · Green", "Machine detail + What-If regression", "Alert centre: ack · assign · feedback"]
for i, (im, cp) in enumerate(zip(imgs, caps)):
    x = LEFT + (i % 2) * Inches(5.5)
    y = Inches(1.05) + (i // 2) * Inches(2.95)
    picture(s, im, x, y, Inches(5.3), Inches(2.5))
    text(s, x, y + Inches(2.5), Inches(5.3), Inches(0.4), cp, size=13, color=MUTED, align=PP_ALIGN.CENTER, italic=True)

# ======================================================================== 12 live demo
s = new_slide("Live Demo", "Switch to the browser. Follow the numbered steps; the whole demo takes three minutes. Before presenting: start with scripts/dev.ps1 or docker compose up, sign in as manager.")
steps = ["Open **Control** → sign in (`manager`)", "**ML anomaly** on Welder-04 → tile turns **Yellow**", "Demo speed ×6 → **Temperature ramp** on CNC-01 → **Orange** with ETA, then **Red**",
         "**Vibration spike** on Press-02 → instant **Red**", "**Alerts**: acknowledge · assign technician · resolve · 👍/👎 feedback", "**Maintenance** log linked to the alert; **Reports** page",
         "**Simulate ML outage** → scores held, rules still alert"]
for i, st in enumerate(steps):
    y = Inches(1.2) + i * Inches(0.76)
    c = s.shapes.add_shape(MSO_SHAPE.OVAL, LEFT, y + Inches(0.04), Inches(0.5), Inches(0.5))
    c.fill.solid()
    c.fill.fore_color.rgb = RED
    c.line.fill.background()
    c.text_frame.text = str(i + 1)
    r = c.text_frame.paragraphs[0].runs[0]
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(16), True, RGBColor(255, 255, 255)
    c.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
    text(s, LEFT + Inches(0.65), y, Inches(10.2), Inches(0.6), st.replace("`", ""), size=19, anchor=MSO_ANCHOR.MIDDLE)

# ======================================================================== 13 Testing & results
s = new_slide("Testing & Results", "All numbers are from real runs of the final code. 28 backend tests, 7 frontend tests, a 13 check end to end smoke test and a MQTT broker kill test. "
                                   "Every performance target from the SRS was met. Be honest that the database layer was verified without live servers.")
big = [("28 + 7", "automated tests passed\n(pytest + Vitest)"), ("13 / 13", "end-to-end smoke checks\n(5 machines, 50 WS clients)"), ("0.5 s", "dashboard update latency\n(p95, target ≤ 1 s)"),
       ("36 ms", "worst-case ML inference\n(target ≤ 200 ms)"), ("2.3 s", "MQTT recovery after broker\nrestart (target ≤ 5 s)"), ("6 / 6", "injected anomalies detected\n0 false alarms on healthy")]
for i, (n, d) in enumerate(big):
    x = LEFT + (i % 3) * Inches(3.68)
    y = Inches(1.25) + (i // 3) * Inches(2.45)
    card(s, x, y, Inches(3.5), Inches(2.25), SOFT["green"] if i % 2 == 0 else SOFT["blue"], None, None)
    text(s, x, y + Inches(0.2), Inches(3.5), Inches(1.0), n, size=40, bold=True, color=GREEN_D, align=PP_ALIGN.CENTER)
    text(s, x, y + Inches(1.2), Inches(3.5), Inches(1.0), d.split("\n"), size=15, color=INK, align=PP_ALIGN.CENTER)
text(s, LEFT, Inches(6.25), Inches(10.9), Inches(0.6), "Orange alert raised with 25 s ETA before Red · Yellow score 97.7 % · fault injection returns HTTP 401 without login", size=14, color=MUTED, italic=True)

# ======================================================================== 14 Advantages / limitations / applications
s = new_slide("Advantages, Limitations & Applications", "Be balanced. Advantages: layered detection, explainable alerts, runs without infrastructure. Limitations: simulated data, one-off training, basic auth. Applications: monitoring, teaching, model test-bench.")
card(s, LEFT, Inches(1.2), Inches(3.5), Inches(5.3), SOFT["green"], "Advantages", [
    "• 3 detection layers", "• Explainable alerts", "• Works with no DB / Docker", "• Operator workflow + audit", "• Tested and documented API"], size=15, title_size=18)
card(s, Inches(5.55), Inches(1.2), Inches(3.55), Inches(5.3), SOFT["orange"], "Limitations", [
    "• Simulated telemetry", "• Model trained once (C-04)", "• Single-tenant Basic auth", "• Linear What-If assumption", "• 2D, desktop-responsive web app"], size=15, title_size=18)
card(s, Inches(9.25), Inches(1.2), Inches(3.65), Inches(5.3), SOFT["blue"], "Applications", [
    "• OEE & condition monitoring", "• Industry 4.0 teaching lab", "• Anomaly-model test bench", "• Pilot for real PLC gateways"], size=15, title_size=18)

# ======================================================================== 15 Conclusion, future scope, references
s = new_slide("Conclusion, Future Scope & References", "Conclusion: the system meets the SRS targets with measured evidence. Future: real equipment via OPC UA, use feedback to retrain, roles and notifications, non-linear RUL. References are in the report.")
card(s, LEFT, Inches(1.2), Inches(5.3), Inches(3.3), SOFT["green"], "Conclusion", [
    "Live OEE + Red / Orange / Yellow alerts in ≈ 0.5 s", "All numeric targets met; ML validated on injected faults",
    "Complete, reproducible, one-command platform"], size=15, title_size=18)
card(s, Inches(7.45), Inches(1.2), Inches(5.45), Inches(3.3), SOFT["blue"], "Future scope", [
    "• Real machines via OPC UA / Modbus → MQTT", "• Retrain from operator feedback", "• Roles, notifications, audit export",
    "• Remaining-useful-life with non-linear models", "• Multi-site deployment, Grafana"], size=15, title_size=18)
text(s, LEFT, Inches(4.7), Inches(10.9), Inches(2.1), [
    "**References**",
    "[1] Nakajima, Introduction to TPM (1988)   [2] ISO 22400-2:2014   [3] Muchiri & Pintelon, IJPR 46(13), 2008",
    "[4] Liu, Ting, Zhou, “Isolation Forest”, IEEE ICDM 2008   [5] Chandola et al., “Anomaly detection: a survey”, ACM CSUR 2009",
    "[6] Pedregosa et al., scikit-learn, JMLR 2011   [7] OASIS MQTT 3.1.1   [8] Lee et al., Manufacturing Letters 3, 2015"], size=13, color=MUTED)

# ======================================================================== move template "Thank you" slide to the end + Q&A notes
sld = prs.slides._sldIdLst
ids = list(sld)
thank = ids[2]
sld.remove(thank)
sld.append(thank)
for sh in prs.slides[len(prs.slides) - 1].shapes:
    if sh.has_text_frame and "Thank" in sh.text_frame.text:
        sh.text_frame.paragraphs[0].runs[0].text = "Thank You !!!  Questions?"
prs.slides[len(prs.slides) - 1].notes_slide.notes_text_frame.text = (
    "Invite questions. Likely ones: Why Isolation Forest? (unsupervised, no fault labels, cheap inference). How is the 85 percent calibrated? (normal tail 70 percent, median anomaly 95 percent). "
    "What happens if the broker or ML fails? (auto-reconnect; last score held). What was not verified? (live InfluxDB/PostgreSQL and Docker were not available on the build machine).")

prs.save(str(OUT))
print("saved", OUT, "slides:", len(prs.slides))
