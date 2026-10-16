"""Build the project presentation on the NMIMS template (docs/templates/Presentation_Format.pptx).

    python presentation/build_pptx.py      # -> presentation/OEE_Smart_Factory_Presentation.pptx

Structure follows the SRS (docs/SRS.docx / the submitted SRS): requirements -> design (UML, DFD) -> implementation -> verification.
All diagrams are native PowerPoint shapes (editable, always sharp); numbers come from the measured test runs.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lxml import etree
from pptx import Presentation

import deckkit as K
from deckkit import *  # noqa: F401,F403

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "docs" / "templates" / "Presentation_Format.pptx"
OUT = ROOT / "presentation" / "OEE_Smart_Factory_Presentation.pptx"
CROP = ROOT / "presentation" / "_crops"
CROP.mkdir(exist_ok=True)

PROJECT_TITLE = "Real-Time OEE and Anomaly Dashboard for a Smart Factory System"

prs = Presentation(str(TEMPLATE))
LAYOUT = prs.slide_layouts.get_by_name("Title and Content")


class Ctx:
    """Shared state handed to the slide modules."""
    prs = prs
    root = ROOT
    crop_dir = CROP


def _strip_placeholders(slide):
    for sh in list(slide.placeholders):
        t = str(sh.placeholder_format.type)
        if "SLIDE_NUMBER" not in t:
            sh._element.getparent().remove(sh._element)


def slide_number(s):
    """Right-aligned page number at exactly the template's own position."""
    box = s.shapes.add_textbox(E(8.83), E(6.97), E(2.33), E(0.4))
    tf = box.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.RIGHT
    fld = etree.SubElement(p._p, qn("a:fld"))
    fld.set("id", "{B6F15528-21DE-4FAA-801E-634DDDAF4B2B}")
    fld.set("type", "slidenum")
    rpr = etree.SubElement(fld, qn("a:rPr"))
    rpr.set("lang", "en-US"), rpr.set("sz", "1200")
    sf = etree.SubElement(rpr, qn("a:solidFill"))
    clr = etree.SubElement(sf, qn("a:srgbClr"))
    clr.set("val", "8C8C8C")
    lat = etree.SubElement(rpr, qn("a:latin"))
    lat.set("typeface", FONT)
    t = etree.SubElement(fld, qn("a:t"))
    t.text = "‹#›"


SLIDE_TITLES: dict[int, str] = {}


def new_slide(title: str, notes: str):
    s = prs.slides.add_slide(LAYOUT)
    SLIDE_TITLES[s.slide_id] = title
    _strip_placeholders(s)
    K.set_current(title)
    tb(s, X0, 0.1, 10.9, 0.55, title, size=28, bold=True, color=WHITE, anchor="m")
    slide_number(s)
    s.notes_slide.notes_text_frame.text = notes
    return s


Ctx.new = staticmethod(new_slide)

# The college template's agenda, in its own order; each section lists the slides (by title) that belong to it.
SECTIONS = [
    ("Introduction", ["The Project in 30 Seconds", "Introduction – What is OEE?"]),
    ("Problem Statement", ["Problem Statement"]),
    ("Objectives", ["Objectives", "UML – Use Case Diagram (SRS §7.2)"]),
    ("Existing vs. Proposed System", ["Existing vs. Proposed System"]),
    ("System Architecture", ["System Architecture", "Data Flow Diagram – Level 1 (Seven Processes)", "UML – Sequence Diagram (SRS §9.2)", "Database Design – ER Diagram (PostgreSQL)"]),
    ("Methodology", ["Methodology"]),
    ("Modules", ["Modules (SRS §3.2)", "UML – Class Diagram: 12 Domain Classes (SRS §8.3)", "Alert Decision Flow – Every 500 ms per Machine",
                 "ML Anomaly Scoring – Isolation Forest", "What-If Degradation & Projection (FR-07)"]),
    ("Technologies Used", ["Technologies Used", "Deployment – Docker Compose & Requirements (SRS §10–11)"]),
    ("Implementation / Screenshots", ["Implementation – Dashboard Screens", "Live Demo – Seven Steps"]),
    ("Results & Testing", ["Testing & Results", "Requirement-to-Test Traceability (SRS §13.3)"]),
    ("Advantages & Applications", ["Advantages, Limitations & Applications"]),
    ("Future Scope", ["Future Scope"]),
    ("Conclusion", ["Conclusion"]),
    ("References", ["References"]),
]
ORDER = [title for _, titles in SECTIONS for title in titles]


def page_range(titles):
    first = ORDER.index(titles[0]) + 3          # slide 1 = title, slide 2 = agenda
    last = ORDER.index(titles[-1]) + 3
    return f"slide {first}" if first == last else f"slides {first} – {last}"


import s_intro   # noqa: E402
import s_design  # noqa: E402
import s_uml     # noqa: E402
import s_result  # noqa: E402

# ============================================================================ slide 1: template title
s1 = prs.slides[0]
for sh in s1.shapes:
    if sh.has_text_frame and "TITLE OF PROJECT" in sh.text_frame.text:
        tf = sh.text_frame
        lines = ["A Presentation on", f"“{PROJECT_TITLE}”", "", "By", "Sanika Jamadar  (Roll No. B291 · 70022400523, Batch A2)", "",
                 "Subject: Software Engineering", "Under the Guidance of  Dr. Naziya Hussain"]
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
            r.font.size = Pt(26 if i == 1 else 20)
            r.font.color.rgb = INK
s1.notes_slide.notes_text_frame.text = (
    "Introduce yourself and the project in one sentence: a software-only smart-factory monitor that shows OEE live and warns operators "
    "three different ways - rules, a machine-learning model and a trend projection - before a machine fails. It is built exactly from my SRS.")

# ============================================================================ slide 2: agenda (template slide, rebuilt on the grid)
s2 = prs.slides[1]
for sh in list(s2.shapes):
    if sh.is_placeholder and "SLIDE_NUMBER" not in str(sh.placeholder_format.type):
        sh._element.getparent().remove(sh._element)
K.set_current("Agenda")
tb(s2, X0, 0.1, 10.9, 0.55, "Agenda", size=28, bold=True, color=WHITE, anchor="m")
agenda = [(name, page_range(titles)) for name, titles in SECTIONS]
colw = (W - 0.4) / 2
rows = 7
rh = (Y1 - 1.25) / rows
for i, (t, r) in enumerate(agenda):
    c, rr = divmod(i, rows)
    x = X0 + c * (colw + 0.4)
    y = 1.25 + rr * rh
    box(s2, x, y, colw, rh - 0.14, "", fill="grey", edge="white", radius=0.1)
    badge(s2, x + 0.38, y + (rh - 0.14) / 2, 0.46, f"{i + 1}", size=15)
    tb(s2, x + 0.8, y + 0.07, colw - 0.9, 0.36, [{"text": t, "size": 17, "bold": True}], anchor="m")
    tb(s2, x + 0.8, y + 0.42, colw - 0.9, 0.2, r, size=12, color=MUTED, anchor="m")
s2.notes_slide.notes_text_frame.text = ("Roadmap in the order of the SRS: requirements first, then design (architecture, UML, data flow), then how it was built, "
                                        "then how it was verified. About 15 minutes plus a 3-minute live demo.")

# ============================================================================ content slides
s_intro.build(Ctx)
s_design.build(Ctx)
s_uml.build(Ctx)
s_result.build(Ctx)

# ============================================================================ order: title, agenda, sections in agenda order, thank-you
sld = prs.slides._sldIdLst
ids = list(sld)
first, agenda_id, thank = ids[0], ids[1], ids[2]
by_title = {SLIDE_TITLES[int(e.get("id"))]: e for e in ids[3:]}
missing = [x for x in ORDER if x not in by_title]
extra = [x for x in by_title if x not in ORDER]
assert not missing and not extra, f"slide titles out of sync - missing: {missing}  not in SECTIONS: {extra}"
for e in ids:
    sld.remove(e)
for e in [first, agenda_id] + [by_title[x] for x in ORDER] + [thank]:
    sld.append(e)
for sh in prs.slides[len(prs.slides) - 1].shapes:
    if sh.has_text_frame and "Thank" in sh.text_frame.text:
        sh.text_frame.paragraphs[0].runs[0].text = "Thank You !!!  Questions?"
        sh.text_frame.paragraphs[0].runs[0].font.size = Pt(40)
prs.slides[len(prs.slides) - 1].notes_slide.notes_text_frame.text = (
    "Invite questions. Likely ones: Why Isolation Forest? (unsupervised, no fault labels needed, very fast inference). How is the 85 percent calibrated? "
    "(normal tail about 70 percent, median anomaly about 95 percent). What if the broker or ML fails? (automatic reconnect; last score held; red rules keep working). "
    "What was verified on real databases? (PostgreSQL and InfluxDB in Docker: data written, read back and still there after a restart).")

try:
    prs.save(str(OUT))
except PermissionError:      # the file is open in PowerPoint: write a sibling instead of failing
    OUT = OUT.with_name(OUT.stem + "_NEW.pptx")
    prs.save(str(OUT))
    print("NOTE: the main file is open in PowerPoint - saved a copy instead.")
print("saved", OUT, "slides:", len(prs.slides))
if K.WARNINGS:
    print("\nPOSSIBLE TEXT OVERFLOW (check these slides):")
    for w in K.WARNINGS:
        print("  -", w)
