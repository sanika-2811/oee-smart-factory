"""Build the project report (.docx) from the college template in docs/templates/.

    python report/build_report.py            # -> report/OEE_Smart_Factory_Project_Report.docx
    (then report/finalize_report.py updates fields / page numbers through Word and exports a PDF)
"""
from __future__ import annotations

import copy
from pathlib import Path

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "docs" / "templates" / "Project_Report_Format.docx"
OUT = ROOT / "report" / "OEE_Smart_Factory_Project_Report.docx"
FIG = ROOT / "report" / "figures"
SHOT = ROOT / "docs" / "screenshots"
CROP = ROOT / "report" / "figures" / "crops"
CROP.mkdir(exist_ok=True)

TITLE = "AI-Enhanced Real-Time OEE and Anomaly Dashboard for a Smart Factory System"
FONT = "Times New Roman"

doc = docx.Document(str(TEMPLATE))
body_start_anchor = doc.paragraphs[-1]           # last (empty) paragraph of the front matter
figure_no = 0
table_no = 0
bookmarks: list[str] = []
bm_id = 100


# ---------------------------------------------------------------- helpers
def set_font(run, size=12, bold=None, italic=None, name=FONT, color=None):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def add_par(text="", style="Body Text", align=WD_ALIGN_PARAGRAPH.JUSTIFY, size=12, bold=False, italic=False, space_after=6, keep=False):
    p = doc.add_paragraph(style=style)
    p.alignment = align
    pf = p.paragraph_format
    pf.space_after, pf.space_before, pf.line_spacing = Pt(space_after), Pt(0), 1.15
    if keep:
        pf.keep_with_next = True
    if text:
        # **bold** inline markup
        parts = text.split("**")
        for i, part in enumerate(parts):
            if part:
                r = p.add_run(part)
                set_font(r, size, bold or i % 2 == 1, italic)
    return p


def bookmark(par, name):
    global bm_id
    bm_id += 1
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), str(bm_id))
    start.set(qn("w:name"), name)
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), str(bm_id))
    par._p.insert(1 if par._p.pPr is not None else 0, start)
    par._p.append(end)
    bookmarks.append(name)


def chapter(num: int, title: str, new_page=True):
    p = doc.add_paragraph(style="Heading 1")
    if new_page:
        p.paragraph_format.page_break_before = True
    r = p.add_run(f"CHAPTER {num}")
    set_font(r, 18, True)
    r.add_break(WD_BREAK.LINE)
    r2 = p.add_run(title)
    set_font(r2, 18, True)
    p.paragraph_format.space_after = Pt(14)
    bookmark(p, f"ch{num}")
    return p


def section(num: str, title: str, bm: bool = True):
    p = doc.add_paragraph(style="Heading 3")
    r = p.add_run(f"{num}  {title}")
    set_font(r, 14, True)
    p.paragraph_format.space_before, p.paragraph_format.space_after = Pt(10), Pt(6)
    p.paragraph_format.keep_with_next = True
    if bm:
        bookmark(p, "s" + num.replace(".", "_"))
    return p


def sub(title: str):
    return add_par(title, align=WD_ALIGN_PARAGRAPH.LEFT, bold=True, size=12, space_after=3, keep=True)


def bullets(items, size=12):
    for it in items:
        p = add_par("", style="List Paragraph", size=size, space_after=2)
        p.paragraph_format.left_indent = Cm(1.0)
        p.paragraph_format.first_line_indent = Cm(-0.5)
        r = p.add_run("•  ")
        set_font(r, size)
        parts = it.split("**")
        for i, part in enumerate(parts):
            if part:
                set_font(p.add_run(part), size, i % 2 == 1)


def code(text: str):
    for line in text.strip().splitlines():
        p = doc.add_paragraph()
        shade = OxmlElement("w:shd")
        shade.set(qn("w:val"), "clear"), shade.set(qn("w:fill"), "F1F5F9")
        p._p.get_or_add_pPr().append(shade)          # first child -> later spacing/ind are inserted after it
        p.paragraph_format.space_after, p.paragraph_format.line_spacing = Pt(0), 1.0
        p.paragraph_format.left_indent = Cm(0.6)
        set_font(p.add_run(line or " "), 8.5, name="Consolas")
    add_par("", space_after=4)


def shade_cell(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"), shd.set(qn("w:color"), "auto"), shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def caption(text: str, kind: str):
    global figure_no, table_no
    if kind == "Figure":
        figure_no += 1
        n = figure_no
    else:
        table_no += 1
        n = table_no
    p = add_par(f"{kind} {n}: {text}", align=WD_ALIGN_PARAGRAPH.CENTER, size=10.5, italic=True, space_after=10)
    return p


def grid_borders(t):
    tblPr = t._tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single"), e.set(qn("w:sz"), "4"), e.set(qn("w:space"), "0"), e.set(qn("w:color"), "94A3B8")
        b.append(e)
    look = tblPr.find(qn('w:tblLook'))
    (look.addprevious(b) if look is not None else tblPr.append(b))


def table(headers, rows, widths=None, cap=None, size=10):
    if cap:
        cp = caption(cap, "Table")
        cp.paragraph_format.keep_with_next = True
        cp.paragraph_format.space_after = Pt(3)
    t = doc.add_table(rows=1, cols=len(headers))
    grid_borders(t)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = ""
        set_font(c.paragraphs[0].add_run(h), size, True)
        shade_cell(c, "DBEAFE")
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            para = cells[i].paragraphs[0]
            para.paragraph_format.space_after = Pt(0)
            parts = str(v).split("**")
            for k, part in enumerate(parts):
                if part:
                    set_font(para.add_run(part), size, k % 2 == 1)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    for row in t.rows:                                   # keep rows together, repeat header
        trPr = row._tr.get_or_add_trPr()
        cs = OxmlElement("w:cantSplit")
        trPr.append(cs)
    add_par("", space_after=6)
    return t


def figure(path: Path, cap: str, width_cm=15.5, max_h_cm=19.0):
    with Image.open(path) as im:
        w, h = im.size
    width = min(width_cm, max_h_cm * w / h)
    p = add_par("", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2, keep=True)
    p.add_run().add_picture(str(path), width=Cm(width))
    caption(cap, "Figure")


def crop(name: str, box: tuple[int, int, int, int], out: str) -> Path:
    with Image.open(SHOT / name) as im:
        im.crop(box).save(CROP / out)
    return CROP / out


def side_by_side(paths, cap, width_each=6.2):
    t = doc.add_table(rows=1, cols=len(paths))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, p_ in enumerate(paths):
        c = t.rows[0].cells[i]
        c.text = ""
        par = c.paragraphs[0]
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        par.add_run().add_picture(str(p_), width=Cm(width_each))
    caption(cap, "Figure")


def field(par, instr: str, placeholder="1", size=12):
    def fc(t):
        r = par.add_run()
        e = OxmlElement("w:fldChar")
        e.set(qn("w:fldCharType"), t)
        r._r.append(e)
        return r
    fc("begin")
    r = par.add_run()
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = f" {instr} "
    r._r.append(it)
    fc("separate")
    set_font(par.add_run(placeholder), size)
    fc("end")


# ================================================================== FRONT MATTER
P = doc.paragraphs
# cover
for p in P[:20]:
    if p.text.strip() == "Project Title":
        for r in p.runs[1:]:
            r._r.getparent().remove(r._r)
        p.runs[0].text = TITLE
        p.runs[0].font.size = Pt(22)
    elif p.text.strip() == "[Name- SAPID]":
        p.runs[0].text = "Sanika Jamadar – Roll No. B291 (Batch A2)"
        for r in p.runs[1:]:
            r._r.getparent().remove(r._r)
    elif p.text.strip().startswith("A Mini Project Report"):
        pass
# acknowledgement
for p in doc.paragraphs[18:30]:
    t = p.text
    if t.startswith("We express our sincere thanks") and "Name" in t:
        for r in p.runs:
            r.text = ""
        p.runs[0].text = ("We express our sincere thanks and gratitude to the Head of Department, Department of Computer Engineering, "
                          "SVKM’S NMIMS, Mukesh Patel School of Technology Management & Engineering, Shirpur Campus (M.H.), for providing the "
                          "necessary resources and help to complete the project work successfully.")
    if t.strip().startswith("Name & Roll No."):
        for r in p.runs[1:]:
            r._r.getparent().remove(r._r)
        p.runs[0].text = "Sanika Jamadar, Roll No. B291 (Batch A2)"
    if t.startswith("We would like to express my special thanks") or t.startswith("Finally, we sincerely"):
        for r in p.runs:
            r.text = r.text.replace("Capstone project", "project")

# abstract text goes after the "ABSTRACT" heading
abs_paras = [p for p in doc.paragraphs if p.text.strip() == "ABSTRACT"]
abs_head = abs_paras[0]
ABSTRACT = [
    "Overall Equipment Effectiveness (OEE) is the standard measure of how well a production asset is used, yet in many plants it is still "
    "computed after the shift from spreadsheets, and faults are found only when a fixed alarm limit is crossed. This project presents a "
    "software-only, AI-enhanced smart-factory dashboard that monitors a virtual factory in real time and warns operators earlier than "
    "threshold alarms can.",
    "A Python Virtual Factory Simulator generates temperature, vibration, operational status and cycle-count telemetry for five (scalable to "
    "twenty) machines every 500 ms and publishes it over MQTT (Eclipse Mosquitto, MQTT over WebSockets). A FastAPI backend validates every "
    "sample, maintains rolling 1-hour and 8-hour OEE (Availability × Performance × Quality), applies deterministic rules for hard faults (RED), "
    "scores each machine with a pre-trained scikit-learn Isolation Forest to raise ML cautions when the anomaly score exceeds 85 % (YELLOW), "
    "and fits a least-squares line y = m·x + c to the last three minutes of temperature to warn up to 60 seconds before a threshold crossing "
    "(ORANGE). Results are pushed over WebSockets to a React and Chart.js dashboard, while telemetry and metadata are stored in InfluxDB and "
    "PostgreSQL (or in memory when no database is configured).",
    "The system was verified with 28 automated backend tests, 7 frontend tests and two end-to-end scripts. In the measured runs, the dashboard "
    "update latency was about 0.5 s (p95), ML inference completed in under 40 ms against a 200 ms target, 50 concurrent WebSocket clients were "
    "served, and the MQTT connection recovered 2.3 s after the broker was restarted. On an independent fault-injection run the Isolation Forest "
    "detected 6 of 6 injected anomalies with 100 % sample precision and no false alarms on healthy machines. The result is a complete, "
    "reproducible, one-command monitoring platform that demonstrates predictive maintenance concepts for Industry 4.0 education.",
    "**Keywords:** OEE, smart factory, anomaly detection, Isolation Forest, MQTT, FastAPI, React, InfluxDB, predictive maintenance.",
]
anchor = abs_head
for txt in ABSTRACT:
    p = doc.add_paragraph(style="Body Text")
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.space_after = Pt(8)
    for i, part in enumerate(txt.split("**")):
        if part:
            set_font(p.add_run(part), 12, i % 2 == 1)
    anchor._p.addnext(p._p)
    anchor = p

# ================================================================== BODY
# ---------------------------------------------------------------- Chapter 1
chapter(1, "INTRODUCTION", new_page=False)
section("1.1", "Background of the Project Topic")
add_par("Manufacturing has entered the era of Industry 4.0, in which machines are instrumented, connected and continuously observed. "
        "The most widely used indicator of how productively an asset is used is **Overall Equipment Effectiveness (OEE)**, introduced in the "
        "Total Productive Maintenance literature and standardised in ISO 22400-2 as a key performance indicator for manufacturing operations. "
        "OEE multiplies three factors: **Availability** (the share of planned time the machine actually runs), **Performance** (how close the "
        "machine runs to its rated speed) and **Quality** (the share of products that are good first time).")
add_par("At the same time, maintenance is moving from reactive repair to predictive maintenance. A hard alarm limit, for example "
        "“temperature above 85 °C”, only fires when damage may already be under way. Two techniques can warn earlier: unsupervised machine "
        "learning, which flags behaviour that is unusual compared with healthy operation, and trend extrapolation, which predicts when a limit "
        "will be crossed if the present drift continues.")
add_par("This project builds a complete software platform, the **AI-Enhanced Real-Time OEE and Anomaly Dashboard for a Smart Factory System**, "
        "that combines both ideas with live OEE reporting. Because no physical plant is required, a Python simulator produces realistic telemetry "
        "and lets the user inject faults on demand, which makes every feature demonstrable and testable.")
section("1.2", "Motivation and Scope of the Report")
add_par("Students rarely get access to a live production line, and commercial manufacturing-execution systems are closed and expensive. The motivation "
        "was to build an open, end-to-end, reproducible system that exercises the full software-engineering life cycle: requirements (SRS), design (UML), "
        "implementation, testing and deployment, while touching real industrial technologies such as MQTT, time-series databases and machine learning.")
add_par("**Scope.** The system is 100 % software-based and uses 2D visualisation only. Machine learning is limited to a pre-trained Isolation Forest "
        "(no deep learning, no online retraining). The product is a desktop-responsive web application with single-tenant HTTP Basic authentication. "
        "These constraints (C-01 to C-07) come directly from the Software Requirements Specification (SRS) prepared earlier in this project, which is the "
        "source of truth for this report.")
section("1.3", "Problem Statement")
add_par("Floor managers and maintenance engineers lack a single, live view that (a) shows the productivity of every machine as OEE, (b) warns about hard "
        "faults immediately, (c) detects subtle abnormal behaviour that fixed limits miss, and (d) predicts a limit breach early enough to act. "
        "The problem addressed is to design and implement such a system that updates within one second, scores anomalies within 200 ms, recovers "
        "from broker failures within five seconds, supports at least 50 concurrent dashboard clients, and keeps working when its databases are unavailable.")
section("1.4", "Salient Contribution")
bullets([
    "A configurable **virtual factory** (5 to 20 machines) with realistic signals, micro-stops, scrap, and four injectable faults.",
    "A **four-colour alert model**: Green normal, Yellow ML caution (score > 85 %), Orange projected fault (least-squares What-If), Red rule-based hard fault.",
    "**Rolling 1 h / 8 h OEE** for every machine and for the plant, computed from O(1) running sums.",
    "A single **Isolation Forest** serving all machines through per-machine normalised features, with a calibrated 0–100 % score and offline validation.",
    "A **storage abstraction** that works fully in memory and switches to InfluxDB + PostgreSQL through configuration only, degrading gracefully if a database is down.",
    "An accessible, responsive **React dashboard** (dark and light themes) with live charts, alert centre, maintenance log, reports and a demo control panel.",
    "A reproducible verification suite: 28 backend tests, 7 frontend tests, an end-to-end smoke test and an MQTT reconnect test.",
])
section("1.5", "Organization of the Report")
table(["Chapter", "Content"], [
    ["1", "Introduction: background, motivation, problem statement, contribution."],
    ["2", "Literature survey on OEE, anomaly detection, MQTT-based industrial IoT and related tools."],
    ["3", "Methodology and implementation: requirements, architecture, algorithms, flow chart, software description and UML models."],
    ["4", "Results and analysis: screenshots of the running system, test results and performance measurements."],
    ["5", "Advantages, limitations and applications."],
    ["6", "Conclusion and future scope, followed by references."],
], widths=[2.2, 13.3], cap="Organisation of the report")

# ---------------------------------------------------------------- Chapter 2
chapter(2, "LITERATURE SURVEY")
section("2.1", "Introduction to the Overall Topic")
add_par("The survey covers four areas that the project combines: (i) OEE as a productivity measure, (ii) anomaly detection for condition monitoring, "
        "(iii) lightweight messaging for industrial IoT, and (iv) the web and database technologies used to build real-time dashboards.")
add_par("**OEE.** Nakajima introduced OEE within Total Productive Maintenance to expose the “six big losses” of equipment. Muchiri and Pintelon reviewed "
        "its use and showed that the Availability × Performance × Quality decomposition is valuable mainly because it points to where losses occur, "
        "which is why this project always displays the three factors next to the final figure. ISO 22400-2 later standardised OEE-related indicators.")
add_par("**Anomaly detection.** Chandola, Banerjee and Kumar survey anomaly detection and distinguish point, contextual and collective anomalies, a "
        "classification that fits machine telemetry. The Isolation Forest of Liu, Ting and Zhou isolates observations with random splits: anomalies need fewer "
        "splits, so their average path length is short. It is unsupervised, needs no fault labels, has linear time complexity and is cheap at inference, "
        "which matches the SRS requirement of a pre-trained model and a 200 ms response.")
add_par("**Industrial messaging.** MQTT, an OASIS standard, is a publish/subscribe protocol with a tiny header that is widespread in industrial IoT and also "
        "runs over WebSockets so that browsers and proxies can take part. Eclipse Mosquitto is its reference open-source broker.")
section("2.2", "Exhaustive Literature Survey")
table(["#", "Work", "Contribution", "Relevance to this project"], [
    ["1", "Nakajima, S. (1988). Introduction to TPM. Productivity Press.", "Origin of OEE and the six big losses.", "Defines the OEE concept implemented in the OEE engine."],
    ["2", "Muchiri, P., Pintelon, L. (2008). Int. J. Production Research 46(13).", "Review of OEE measurement and practice.", "Justifies showing A, P and Q separately."],
    ["3", "ISO 22400-2:2014. Automation systems and integration - KPIs for manufacturing operations management.", "Standard definitions of manufacturing KPIs.", "Formal basis for the OEE and downtime reports."],
    ["4", "Liu, F. T., Ting, K. M., Zhou, Z.-H. (2008). Isolation Forest. IEEE ICDM, 413-422.", "Tree-based unsupervised anomaly detector.", "The ML model used for YELLOW cautions."],
    ["5", "Liu, F. T., Ting, K. M., Zhou, Z.-H. (2012). Isolation-based anomaly detection. ACM TKDD 6(1).", "Extended analysis, sub-sampling, complexity.", "Guides the choice of max_samples and trimmed training."],
    ["6", "Chandola, V., Banerjee, A., Kumar, V. (2009). Anomaly detection: a survey. ACM Computing Surveys 41(3).", "Taxonomy of anomaly types and methods.", "Frames hard-fault rules versus subtle ML anomalies."],
    ["7", "Pedregosa, F. et al. (2011). Scikit-learn: Machine learning in Python. JMLR 12.", "The library implementing IsolationForest.", "Training and inference (model.pkl)."],
    ["8", "Banks, A., Gupta, R. (2014). MQTT Version 3.1.1. OASIS Standard.", "Lightweight publish/subscribe protocol.", "Telemetry transport between simulator and backend."],
    ["9", "Lee, J., Bagheri, B., Kao, H.-A. (2015). A cyber-physical systems architecture for Industry 4.0-based manufacturing systems. Manufacturing Letters 3.", "5C architecture: connection, conversion, cyber, cognition, configuration.", "The pipeline maps onto connection (MQTT), conversion (OEE), cognition (ML)."],
], widths=[0.8, 5.6, 4.4, 4.7], cap="Summary of the literature reviewed", size=9)
add_par("**Gap addressed.** The surveyed works treat OEE, anomaly detection and messaging separately. This project integrates them in one runnable, "
        "tested system with an operator workflow (acknowledge, assign, resolve, feedback), and adds a transparent early-warning layer based on linear "
        "extrapolation that complements the black-box ML score.")

# ---------------------------------------------------------------- Chapter 3
chapter(3, "METHODOLOGY AND IMPLEMENTATION")
section("3.1", "Overview of Methodology")
add_par("The work followed an iterative, requirements-driven process. The SRS fixed twelve functional requirements (FR-01 to FR-12) and non-functional targets "
        "(NFR-P, R, M, S, SC, U). The system was then built in milestones, each ending with tests and a commit:")
table(["Milestone", "Deliverable", "Verified by"], [
    ["M1", "Repository, virtual factory simulator, Mosquitto configuration", "Statistics check of 8 h of simulated data"],
    ["M2", "FastAPI ingest, validation, WebSocket fan-out (memory store)", "pytest API tests, smoke test"],
    ["M3", "OEE engine, rule engine, What-If regression", "Unit tests with exact OEE arithmetic"],
    ["M4", "Isolation Forest training, calibration, batched scoring", "Offline fault-injection validation"],
    ["M5", "Alerts, maintenance, feedback, HTTP Basic auth", "API tests (401 / 422 / 404 paths)"],
    ["M6", "React dashboard, six screens, visual QA at 1440 px and 390 px", "Type-check, build, Playwright screenshots"],
    ["M7", "Storage db mode (InfluxDB + PostgreSQL), verification tool", "SQL parsed with the PostgreSQL grammar; outage test"],
    ["M8", "Docker Compose, Dockerfiles, nginx, scripts", "Compose file validation"],
    ["M9", "Test suites, smoke test, MQTT reconnect test", "28 + 7 tests, 13 + 6 end-to-end checks"],
], widths=[2.0, 8.0, 5.5], cap="Development milestones")
sub("Requirements implemented")
table(["ID", "Requirement (abridged)", "Implementation"], [
    ["FR-01", "5 machines, 500 ms telemetry over MQTT/WebSockets", "simulator/run.py, paho-mqtt with websockets transport"],
    ["FR-02", "OEE = A × P × Q, rolling 1 h and 8 h", "services/oee.py (5 s buckets, running sums)"],
    ["FR-03", "Hard rule alerts (e.g. temperature > 85 °C)", "services/rules.py, per-machine limits"],
    ["FR-04", "Isolation Forest score 0-100 %, Yellow above 85 %", "ml/ (train.py, scorer.py, features.py)"],
    ["FR-05", "React 2D dashboard, four colours, Chart.js, alert feed, gauge", "frontend/src (6 pages)"],
    ["FR-06", "Maintenance CRUD, acknowledge, technician, feedback", "api/routes.py, services/alerts.py"],
    ["FR-07", "What-If: 3-minute temperature rise, y = mx + c, Orange at 60 s", "services/whatif.py, simulator temp_ramp fault"],
    ["FR-08", "7-day OEE, downtime per shift, ML accuracy reports", "/reports/* endpoints, Reports page"],
    ["FR-09", "Reject invalid telemetry", "Pydantic TelemetryIn model; POST /telemetry gateway"],
    ["FR-10", "Basic authentication for write operations", "core/auth.py (PBKDF2 hashes), login dialog"],
    ["FR-11", "Scale from 5 to 20 machines by configuration", "MACHINE_COUNT, simulator/profiles.py"],
    ["FR-12", "OpenAPI documentation at /docs", "FastAPI automatic documentation"],
], widths=[1.6, 7.2, 6.7], cap="Mapping of functional requirements to the implementation", size=9.5)

section("3.2", "Model Architectures Implemented")
add_par("The system is organised as five cooperating components (Figure 1): the simulator, the MQTT broker, the FastAPI backend, the data stores and the "
        "React dashboard. The backend is a single asyncio process; all engine logic runs on the event-loop thread, so no locks are needed. A 500 ms tick "
        "performs batched ML inference, What-If projection, alert evaluation and snapshot broadcast.")
figure(FIG / "architecture.png", "System architecture", 16)
sub("(a) OEE engine")
add_par("Samples are folded into 5-second buckets, and a rolling window keeps running sums over the buckets that fall inside it. Reading the 1 h or 8 h OEE is "
        "therefore O(1) irrespective of the number of samples. With Δt the time between samples:")
code("""Availability = run_time / planned_time                  (planned_time = observed time)
Performance  = (cycles x ideal_cycle_time) / run_time    (capped at 100 %)
Quality      = good_cycles / total_cycles
OEE          = Availability x Performance x Quality""")
add_par("Cycle counters are cumulative, so deltas are used and a counter reset (simulator restart) is treated as a re-baseline. Gaps longer than 30 s are "
        "treated as missing data rather than downtime. Plant OEE is computed from the summed components of all machines, not by averaging percentages.")
sub("(b) Rule engine (RED)")
add_par("A deterministic IF-THEN-ELSE evaluator raises RED when temperature or vibration exceeds the machine’s configurable hard limit, or when the machine "
        "reports STOPPED. Limits are held per machine (for example 85 °C for the CNC mill and 90 °C for the welder) and can be changed from the dashboard.")
sub("(c) Isolation Forest (YELLOW)")
add_par("One model serves every machine because inputs are normalised per machine. Six features are used: the temperature and vibration deviations from the "
        "machine’s nominal operating point (z_temp, z_vib), the 10-second temperature change (z_dtemp), the 10-second vibration standard deviation (z_vstd), and "
        "two joint-magnitude features (z_level, z_dyn). Training data are generated synthetically by running the simulator without faults (1.5 h of normal "
        "telemetry for 20 machine profiles, 68 687 rows). The 0.3 % most extreme rows are trimmed and the forest (200 trees, max_samples = 1024) is refitted.")
add_par("A raw Isolation Forest score s lies in (0, 1). It is converted to a 0–100 % Anomaly Score by piecewise-linear calibration with three anchors: the median "
        "normal score maps to 8 %, the 99.9th percentile of normal scores to 70 %, and the median score of injected anomalies to 95 %. The threshold of 85 % therefore "
        "lies between the tail of healthy data and the typical fault. A caution is raised after two consecutive ticks above 85 %. Windows that include a status "
        "transition (for example idle to running) are not scored, because start-up transients are normal but look unusual to the model.")
add_par("A notable design lesson is that an Isolation Forest does not extrapolate: points far outside the training range receive scores similar to the most extreme "
        "training points. Adding the two joint-magnitude features and trimming the training tail restored a clear gap between healthy and faulty data (Section 4.3).")
sub("(d) What-If projection (ORANGE)")
add_par("The temperature of each running machine is sampled once per second into a 180-point buffer. Ordinary least squares gives the line y = m·x + c, where x is the time in seconds "
        "since the start of the window:")
code("""m = (n·Σxy − Σx·Σy) / (n·Σx² − (Σx)²)        c = (Σy − m·Σx) / n
ETA = (limit − (m·x_now + c)) / m             R² = 1 − SS_res / SS_tot""")
add_par("ORANGE is raised when 0 < ETA ≤ 60 s, subject to guards that suppress noise: at least 30 samples, slope m ≥ 0.03 °C/s and R² ≥ 0.6. The dashboard draws the "
        "points, the fitted line extended 60 s into the future, the hard limit and the ETA.")
sub("(e) Alert manager")
add_par("Priority is RED > ORANGE > YELLOW > GREEN. RED opens immediately; ORANGE and YELLOW need two consecutive ticks (debounce). A lower-level alert is closed only "
        "after a higher one has opened, which avoids a flash of green while escalating, and each alert clears after its condition has been absent for 3–4 s. "
        "An alert moves through open, acknowledged, resolved (or auto-cleared), and operators can assign a virtual technician and mark it a true or false positive.")

section("3.3", "Flow Chart")
add_par("Figure 2 shows the decision flow executed for every machine on every tick. Hard rules are evaluated first because they are the most reliable and urgent; "
        "the projection and the ML score follow.")
figure(FIG / "alert_flow.png", "Alert decision flow", 14.5, 15.5)

section("3.4", "Hardware description")
add_par("The platform is deliberately hardware-free (constraint C-01): the machines are simulated and no PLC, sensor or gateway is required. The development and "
        "test machine used for all measurements in this report was an ordinary Windows 11 laptop. The SRS minimum is a dual-core 2.0 GHz processor, 8 GB RAM, 20 GB "
        "of free storage and a 1366 × 768 display; a quad-core CPU with 16 GB RAM is recommended when the databases run alongside the application.")
add_par("In a real deployment the simulator would be replaced by a gateway publishing the same JSON payload to the same MQTT topics (factory/telemetry/<machine_id>), "
        "so no other component would need to change.")

section("3.5", "Software description")
table(["Layer", "Technology", "Purpose"], [
    ["Simulator", "Python 3 (standard library), paho-mqtt 2", "Signals, faults, 500 ms publisher, MQTT control channel"],
    ["Broker", "Eclipse Mosquitto 2 (TCP 1883, WebSocket 9001)", "Transient transport; auto-reconnect 1-5 s"],
    ["Backend", "FastAPI, Uvicorn, Pydantic v2, asyncio", "Ingest, validation, engines, REST, WebSocket, OpenAPI"],
    ["Machine learning", "scikit-learn IsolationForest, NumPy, joblib", "Training, calibration, batched inference"],
    ["Time series", "InfluxDB v2 (raw 30 d, aggregated 1 y)", "Telemetry, anomaly scores, hourly OEE roll-ups"],
    ["Relational", "PostgreSQL 14 via SQLAlchemy", "Machines, users, alerts, maintenance, feedback, model registry"],
    ["Frontend", "React 18, TypeScript, Vite, Chart.js", "Dashboard, six screens, light and dark themes"],
    ["Deployment", "Docker Compose, nginx", "One-command start-up (databases optional via profile)"],
    ["Quality", "pytest, Vitest, Playwright", "Unit, API, end-to-end and visual checks"],
], widths=[3.0, 6.0, 6.5], cap="Technology stack", size=9.5)
sub("Repository layout")
code("""simulator/   virtual factory + MQTT publisher          backend/app/  api, core, services, ml, storage, ws
frontend/    React + Vite + Chart.js                  db/           postgres_schema.sql, influx_setup.md
deploy/      mosquitto.conf                           scripts/      smoke_test, mqtt_resilience_test, screenshots
docker-compose.yml   .env.example   Makefile   docs/   report/   presentation/""")
sub("Telemetry contract")
code("""MQTT topic: factory/telemetry/CNC-01
{"machine_id":"CNC-01","ts":1792066318.24,"temperature":62.31,"vibration":2.41,
 "status":"RUNNING","cycle_count":44249,"good_count":43370}""")
add_par("Every payload is validated (FR-09): negative temperature or vibration, an unknown status string, a malformed machine id or a negative cycle count is rejected and "
        "counted in the metrics instead of being processed.")
sub("Non-functional design decisions")
bullets([
    "**Latency (NFR-P1).** Samples are processed on arrival; the 500 ms tick adds at most one tick of delay. Measured emission-to-broadcast p95 is about 0.5 s.",
    "**Inference (NFR-P2).** All machines are scored in one batched call per tick (about 15 ms for five machines).",
    "**Reliability (NFR-R1/R2).** If scoring fails the last known score is held and RED rules continue; the MQTT client reconnects with 1 to 5 s back-off.",
    "**Security (NFR-S).** HTTP Basic with PBKDF2-hashed passwords, no secrets in code (.env), validation on every endpoint.",
    "**Scalability (NFR-SC).** MACHINE_COUNT up to 20; per-client WebSocket queues so a slow browser cannot delay others.",
    "**Resilience of storage.** Database writes are queued and batched (about every 1 s); a database outage is logged and retried while the dashboard keeps running from memory.",
    "**History back-fill.** On start-up the simulator fast-forwards seven simulated days so that the 1 h / 8 h OEE windows and the 7-day reports are meaningful immediately. "
    "This history is clearly labelled as simulated in the interface.",
])

section("3.6", "Model Development (UML Diagram)")
add_par("The SRS defines twelve domain classes and several UML artefacts. The following diagrams were redrawn from the SRS and the implementation so that they match the delivered code.")
figure(FIG / "usecase.png", "Use case diagram (UC-1 to UC-9, UC-14, UC-15, UC-17)", 15.5, 12.5)
figure(FIG / "class_diagram.png", "Class diagram of the twelve domain classes", 16, 12)
figure(FIG / "sequence.png", "Sequence diagram: ingestion, alerting and operator actions", 16, 14)
figure(FIG / "er_diagram.png", "PostgreSQL entity-relationship diagram", 15.5, 11)

# ---------------------------------------------------------------- Chapter 4
chapter(4, "RESULT AND ANALYSIS")
section("4.1", "Implementation & Screen Shot")
add_par("All screenshots below were captured from the running application with Playwright at 1440 px width (and 390 px for the phone views). "
        "The fault scenario was produced with the Control page: an ML anomaly on the welder, a temperature ramp on the CNC mill (compressed to 30 s with the demo-speed control) "
        "and a vibration spike on the hydraulic press.")
figure(SHOT / "desktop_01_overview_normal.png", "Plant overview in normal operation: OEE gauge with A / P / Q rings, KPI cards and machine health tiles", 14.5, 18.5)
figure(SHOT / "desktop_04_machines_alerts.png", "Machine grid with RED (CNC mill, hydraulic press), ORANGE with ETA (welder) and GREEN machines", 15.5, 14)
figure(crop("desktop_05_machine_detail_whatif.png", (0, 0, 1440, 1160), "detail_top.png"),
       "Machine detail: live temperature/vibration chart, anomaly-score gauge and the What-If regression line crossing the 85 °C limit", 15.5, 17.5)
figure(crop("desktop_07_alerts_centre_actioned.png", (0, 0, 1440, 1250), "alerts_top.png"),
       "Alert centre after operator actions: acknowledgement, assigned technician, true-positive feedback", 15.5, 17)
figure(SHOT / "desktop_08_maintenance.png", "Maintenance timeline and the log form (records can be linked to alerts)", 15.5, 14)
figure(SHOT / "desktop_09_reports.png", "Reports: 7-day OEE trend, downtime per shift and ML accuracy", 15.5, 15)
figure(SHOT / "desktop_10_control.png", "Control page: fault injection, demo speed, live non-functional targets and system health", 15.5, 13)
side_by_side([SHOT / "mobile_02_machines_normal.png", SHOT / "mobile_04_machines_alerts.png"],
             "Phone layout (390 px): machine tiles in normal operation (left) and during faults (right)", 5.6)
side_by_side([crop("desktop_11_light_theme.png", (0, 0, 1440, 900), "light_top.png"), SHOT / "desktop_12_login.png"],
             "Light theme (left) and the sign-in dialog with demo accounts (right)", 7.6)

section("4.2", "Test Results", bm=False)
add_par("The tests below were run on the final code. Numbers are copied from the actual test output.")
table(["Suite", "Scope", "Result"], [
    ["pytest (backend)", "OEE maths, rules, What-If regression, ML scoring, alert lifecycle, validation, API contract, authentication, CRUD, WebSocket", "**28 passed**"],
    ["Vitest (frontend)", "Formatting, duration/time helpers, OEE formula and grading, anomaly bands", "**7 passed**"],
    ["TypeScript + Vite build", "Strict type-check and production bundle (about 400 kB JS, 130 kB gzip)", "**passed**"],
    ["scripts/smoke_test.py", "Starts the backend in direct mode and exercises the whole flow", "**13 / 13 checks passed**"],
    ["scripts/mqtt_resilience_test.py", "Real MQTT path with broker kill / restart", "**6 / 6 checks passed**"],
], widths=[4.2, 8.6, 2.7], cap="Automated test summary", size=9.5)
table(["End-to-end check", "Observed result"], [
    ["Five machines streaming", "5 of 5 live"],
    ["OEE (1 h) within 0-100 %", "84.2 %  (A 97.4, P 88.1, Q 98.1)"],
    ["OEE (8 h) available", "83.7 %"],
    ["50 concurrent WebSocket clients", "50 / 50 received at least 3 snapshots"],
    ["Write operation without credentials", "HTTP 401"],
    ["Temperature ramp -> ORANGE (What-If)", "raised with ETA 25.3 s"],
    ["Temperature above limit -> RED", "85.1 °C exceeds the 85 °C hard limit"],
    ["ML anomaly -> YELLOW", "anomaly score 97.7 %"],
    ["Dashboard update latency (emission to broadcast)", "p95 502 ms, max 519 ms  (target <= 1000 ms)"],
    ["ML inference time", "p95 15.7 ms, max 35.9 ms  (target <= 200 ms)"],
    ["MQTT: fault injected through the control channel", "RED alert after 1.5 s"],
    ["MQTT: broker killed and restarted", "backend reconnected and data resumed 2.3 s after the broker accepted connections (target <= 5 s)"],
], widths=[7.5, 8.0], cap="End-to-end measurements (smoke test and MQTT resilience test)", size=9.5)
add_par("The 500 ms latency figure is dominated by the sampling phase of the 500 ms tick (a sample waits on average 250 ms and at most 500 ms for the next tick). "
        "The browser round-trip measured on the Control page was a few milliseconds on the same machine.")

section("4.3", "Machine-learning evaluation", bm=False)
add_par("The model was validated on an independent simulator run (different random seed) in which six faults were injected into ten machines (three bearing-wear "
        "anomalies and three vibration spikes), leaving four machines healthy. A sample counts as faulty from 8 s after the fault starts until it ends.")
table(["Metric", "Value"], [
    ["Faults injected / detected (two consecutive samples above 85 %)", "6 / 6  (event recall 100 %)"],
    ["Sample precision", "100 %"],
    ["Sample recall", "79.5 %"],
    ["False alarms on healthy machines", "0 per hour"],
    ["Training set", "68 687 normal rows (20 machine profiles, trimmed 0.3 % tail)"],
    ["Healthy-data 99th percentile score (smoke run)", "below 85 % (pytest asserts this)"],
], widths=[10.0, 5.5], cap="Isolation Forest validation against injected faults", size=10)
add_par("A first version using only four features scored healthy and faulty data almost identically (sample precision 27 %), because the Isolation Forest does not "
        "extrapolate beyond the training range. Scoring only clean RUNNING windows, adding the two joint-magnitude features and trimming the training tail raised precision to 100 % with no false alarms; "
        "this iteration is a useful illustration of why a model must be validated against injected faults rather than trusted by default.")

section("4.4", "Discussion", bm=False)
bullets([
    "**Orange before Red.** In the ramp scenario the Orange warning appeared with a 25-60 s lead time before the Red threshold was crossed, which is the early-warning behaviour required by FR-07.",
    "**Yellow without Red.** The bearing-wear fault keeps temperature and vibration below every hard limit, so only the ML model notices it: exactly the “subtle degradation” case in the SRS.",
    "**Graceful degradation.** With the ML service switched off from the Control page the last score is held and RED rules still work; with unreachable databases the application starts in about 4 s and reports each database separately as unreachable.",
    "**Honest limits of the evidence.** The InfluxDB / PostgreSQL code was verified by parsing all SQL with the PostgreSQL grammar, by the outage test and by code review, but "
    "it could not be run against live servers in the build environment (no Docker). The student should run `python -m app.storage.verify` after creating the databases. "
    "Likewise the Docker Compose stack was validated syntactically but not started on the build machine.",
])

# ---------------------------------------------------------------- Chapter 5
chapter(5, "ADVANTAGE, LIMITATIONS AND APPLICATIONS")
section("5.1", "Advantages")
bullets([
    "Three complementary detection layers (rules, projection, ML) give both certainty and early warning.",
    "Runs end to end with **no database and no Docker** for development, and scales to the full stack by configuration only.",
    "Every number on screen is live; the OEE breakdown makes the cause of lost productivity visible.",
    "Explainable alerts: each alert states the rule, the limit, the ETA or the score that triggered it.",
    "Operator workflow and feedback produce an audit trail and an ML accuracy report.",
    "Open technologies, documented API (/docs), tested code and one-command deployment make the system easy to reproduce and extend.",
])
section("5.2", "Limitations")
bullets([
    "Telemetry is simulated; real sensors would add noise, missing data, clock drift and calibration issues.",
    "The Isolation Forest is trained once offline and not retrained; operator feedback is collected but not yet used to adapt the model (constraint C-04).",
    "Authentication is single-tenant HTTP Basic; there is no per-role permission model or password reset.",
    "The What-If projection assumes an approximately linear temperature trend; sudden or non-linear failures are caught by rules and ML instead.",
    "The mini-project uses a simple back-fill for history; accurate long-term history requires the databases and a real run time.",
    "The dashboard is a 2D, desktop-responsive web application, not a native mobile app.",
])
section("5.3", "Applications")
bullets([
    "Condition monitoring and OEE dashboards for discrete-manufacturing lines (machining, pressing, welding, packaging).",
    "Teaching Industry 4.0, predictive maintenance and software engineering in laboratories without physical equipment.",
    "A test bench for evaluating anomaly-detection models and alert strategies with reproducible fault injection.",
    "A starting point for a digital twin or a pilot connecting real PLC gateways to the same MQTT topics.",
])

# ---------------------------------------------------------------- Chapter 6
chapter(6, "CONCLUSION AND FUTURE SCOPE")
add_par("This project delivered a complete AI-enhanced OEE and anomaly dashboard that satisfies the SRS requirements that could be verified in the build environment. "
        "Five virtual machines stream telemetry every 500 ms over MQTT; the backend validates it, computes rolling OEE, raises RED, ORANGE and YELLOW alerts with a clear priority, "
        "and pushes results to a responsive React dashboard in about half a second. The measured behaviour met every numeric target: latency below 1 s, inference below 200 ms "
        "(35.9 ms worst case), 50 concurrent WebSocket clients, and MQTT recovery in 2.3 s against a 5 s target. The Isolation Forest detected all injected anomalies with no false alarms "
        "on healthy machines, and the work highlighted the importance of validating ML models with injected faults.")
add_par("From a software-engineering viewpoint the project shows the value of writing requirements first, building in verified milestones, keeping domain logic pure and "
        "testable, and designing for failure (graceful degradation, reconnection, validation).")
sub("Future scope")
bullets([
    "Connect real equipment through an OPC UA / Modbus gateway publishing to the same MQTT topics.",
    "Use the collected true/false-positive feedback to re-calibrate the anomaly threshold per machine and to retrain the model offline.",
    "Add per-role permissions, audit export and email / chat notifications for RED alerts.",
    "Add remaining-useful-life estimation with non-linear trend models and compare it with the linear What-If projection.",
    "Move to a multi-site deployment with Kubernetes, authentication through an identity provider and a Grafana view of the InfluxDB data.",
    "Add a 3D digital-twin view (outside the current SRS constraints) and shift-level OEE targets with automatic loss categorisation.",
])
p = add_par("References", style="Heading 2")
for r in p.runs:
    set_font(r, 16, True)
bookmark(p, "refs")
REFS = [
    "S. Nakajima, Introduction to TPM: Total Productive Maintenance. Portland, OR: Productivity Press, 1988.",
    "P. Muchiri and L. Pintelon, “Performance measurement using overall equipment effectiveness (OEE): literature review and practical application discussion,” Int. J. Production Research, vol. 46, no. 13, pp. 3517-3535, 2008.",
    "ISO 22400-2:2014, Automation systems and integration - Key performance indicators (KPIs) for manufacturing operations management - Part 2: Definitions and descriptions.",
    "F. T. Liu, K. M. Ting and Z.-H. Zhou, “Isolation Forest,” in Proc. IEEE Int. Conf. Data Mining (ICDM), 2008, pp. 413-422.",
    "F. T. Liu, K. M. Ting and Z.-H. Zhou, “Isolation-based anomaly detection,” ACM Trans. Knowledge Discovery from Data, vol. 6, no. 1, 2012.",
    "V. Chandola, A. Banerjee and V. Kumar, “Anomaly detection: a survey,” ACM Computing Surveys, vol. 41, no. 3, 2009.",
    "F. Pedregosa et al., “Scikit-learn: Machine learning in Python,” J. Machine Learning Research, vol. 12, pp. 2825-2830, 2011.",
    "A. Banks and R. Gupta (eds.), MQTT Version 3.1.1, OASIS Standard, 2014.",
    "J. Lee, B. Bagheri and H.-A. Kao, “A cyber-physical systems architecture for Industry 4.0-based manufacturing systems,” Manufacturing Letters, vol. 3, pp. 18-23, 2015.",
    "FastAPI documentation, https://fastapi.tiangolo.com; React documentation, https://react.dev; Chart.js documentation, https://www.chartjs.org.",
    "InfluxDB v2 documentation, https://docs.influxdata.com; PostgreSQL 14 documentation, https://www.postgresql.org/docs/14; Eclipse Mosquitto, https://mosquitto.org.",
    "Software Requirements Specification: AI-Enhanced Real-Time OEE and Anomaly Dashboard for a Smart Factory System, version 1.0, September 2026.",
]
for i, r in enumerate(REFS, 1):
    p = add_par(f"[{i}]  {r}", align=WD_ALIGN_PARAGRAPH.LEFT, size=11, space_after=4)
    p.paragraph_format.left_indent, p.paragraph_format.first_line_indent = Cm(1.0), Cm(-1.0)

# ================================================================== TOC fill (PAGEREF fields)
toc = doc.tables[0]
order = iter(bookmarks)
mapping = ["ch1", "s1_1", "s1_2", "s1_3", "s1_4", "s1_5", "ch2", "s2_1", "s2_2", "ch3", "s3_1", "s3_2", "s3_3", "s3_4", "s3_5", "s3_6",
           "ch4", "s4_1", "ch5", "s5_1", "s5_2", "s5_3", "ch6", "refs"]
mi = iter(mapping)
for row in toc.rows[1:]:
    paras2 = [p for p in row.cells[2].paragraphs if p.text.strip()]
    if not paras2:
        continue
    page_cell = row.cells[3]
    for p in list(page_cell.paragraphs):
        for r in p.runs:
            r._r.getparent().remove(r._r)
    # one paragraph per title line, aligned with the title paragraphs of column 3 (blank lines keep spacing)
    ps3 = page_cell.paragraphs
    idx_nonblank = [i for i, p in enumerate(row.cells[2].paragraphs) if p.text.strip()]
    for k in idx_nonblank:
        while len(ps3) <= k:
            page_cell.add_paragraph()
            ps3 = page_cell.paragraphs
        bm = next(mi)
        ps3[k].alignment = WD_ALIGN_PARAGRAPH.CENTER
        field(ps3[k], f"PAGEREF {bm} \\h", "1", 12)

# ================================================================== footer page numbers + restart at 1 for the body
last = doc.sections[-1]
last.footer.is_linked_to_previous = False
fp = last.footer.paragraphs[0]
fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
for r in list(fp.runs):
    r._r.getparent().remove(r._r)
field(fp, "PAGE", "1", 11)
pg = OxmlElement("w:pgNumType")
pg.set(qn("w:start"), "1")
last._sectPr.find(qn('w:pgMar')).addnext(pg)

# update fields on open
settings = doc.settings.element
uf = OxmlElement("w:updateFields")
uf.set(qn("w:val"), "true")
anchor_el = None
for tag in ("w:hdrShapeDefaults", "w:footnotePr", "w:endnotePr", "w:compat"):
    anchor_el = settings.find(qn(tag))
    if anchor_el is not None:
        break
(anchor_el.addprevious(uf) if anchor_el is not None else settings.append(uf))

doc.core_properties.title = TITLE
doc.core_properties.author = "Sanika Jamadar"
doc.save(str(OUT))
print("saved", OUT, "| figures:", figure_no, "tables:", table_no)
