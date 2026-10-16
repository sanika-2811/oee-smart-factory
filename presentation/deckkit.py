"""Small drawing kit on top of python-pptx: one grid, one font, native shapes and connectors.

Everything is positioned in inches on a fixed grid so text and shapes line up exactly:
    content area  x = 1.95 .. 12.90 in (right of the logo tab),  y = 1.10 .. 6.95 in
"""
from __future__ import annotations

import math
from pathlib import Path

from lxml import etree
from PIL import Image
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

FONT = "Times New Roman"
X0, W = 1.95, 10.95            # content left edge / width
X1 = X0 + W                    # 12.90
Y0, Y1 = 1.10, 6.90            # content top / bottom
GAP = 0.25

INK = RGBColor(0x11, 0x18, 0x27)
MUTED = RGBColor(0x47, 0x55, 0x69)
SLATE = RGBColor(0x64, 0x74, 0x8B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
RED = RGBColor(0xC0, 0x00, 0x00)
GREEN_D = RGBColor(0x37, 0x56, 0x23)
SOFT = {"green": RGBColor(0xDC, 0xFC, 0xE7), "yellow": RGBColor(0xFE, 0xF9, 0xC3), "orange": RGBColor(0xFF, 0xED, 0xD5),
        "red": RGBColor(0xFE, 0xE2, 0xE2), "blue": RGBColor(0xDB, 0xEA, 0xFE), "grey": RGBColor(0xF1, 0xF5, 0xF9),
        "violet": RGBColor(0xED, 0xE9, 0xFE), "cyan": RGBColor(0xCF, 0xFA, 0xFE), "white": WHITE}
EDGE = {"green": RGBColor(0x16, 0xA3, 0x4A), "yellow": RGBColor(0xCA, 0x8A, 0x04), "orange": RGBColor(0xEA, 0x58, 0x0C),
        "red": RGBColor(0xDC, 0x26, 0x26), "blue": RGBColor(0x25, 0x63, 0xEB), "grey": RGBColor(0x64, 0x74, 0x8B),
        "violet": RGBColor(0x7C, 0x3A, 0xED), "cyan": RGBColor(0x08, 0x91, 0xB2), "white": RGBColor(0xCB, 0xD5, 0xE1)}
LEVEL = {"green": RGBColor(0x22, 0xC5, 0x5E), "yellow": RGBColor(0xFA, 0xCC, 0x15), "orange": RGBColor(0xFB, 0x92, 0x3C),
         "red": RGBColor(0xEF, 0x44, 0x44)}

WARNINGS: list[str] = []
_CURRENT = {"title": ""}


def E(v: float) -> Emu:
    return Inches(v)


def cols(n: int, gap: float = GAP, x0: float = X0, w: float = W) -> list[tuple[float, float]]:
    cw = (w - gap * (n - 1)) / n
    return [(x0 + i * (cw + gap), cw) for i in range(n)]


# ----------------------------------------------------------------------------- text
def _est_height(paras, w, size, margin_lr) -> float:
    avail = max(0.1, (w - 2 * margin_lr)) * 72
    total = 0.0
    for p in paras:
        d = p if isinstance(p, dict) else {"text": p}
        sz = d.get("size", size)
        txt = d["text"].replace("**", "")
        a = avail - (16 if d.get("bullet") else 0)
        cw = sz * (0.50 if d.get("bold") else 0.46) * 1.07
        lines = max(1, math.ceil(len(txt) * cw / a)) if txt else 1
        total += lines * sz * 1.2 + d.get("space_after", 0)
    return total / 72


def _fill_paras(tf, paras, size, bold, color, align, italic, font=FONT):
    first = True
    for item in paras:
        d = item if isinstance(item, dict) else {"text": item}
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        sz = d.get("size", size)
        p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[d.get("align", align)]
        p.space_after = Pt(d.get("space_after", 0))
        p.space_before = Pt(d.get("space_before", 0))
        if d.get("bullet"):
            pPr = p._p.get_or_add_pPr()
            pPr.set("marL", str(int(0.22 * 914400)))
            pPr.set("indent", str(-int(0.22 * 914400)))
            bf = etree.SubElement(pPr, qn("a:buFont"))
            bf.set("typeface", "Arial")
            bu = etree.SubElement(pPr, qn("a:buChar"))
            bu.set("char", "•")
        parts = d["text"].split("**")
        for k, part in enumerate(parts):
            if not part:
                continue
            r = p.add_run()
            r.text = part
            r.font.name, r.font.size = font, Pt(sz)
            r.font.bold = d.get("bold", bold) or k % 2 == 1
            r.font.italic = d.get("italic", italic)
            r.font.color.rgb = d.get("color", color)


def _check(paras, w, h, size, margin_lr, margin_tb):
    need = _est_height(paras, w, size, margin_lr) + 2 * margin_tb
    if need > h + 0.02:
        first = paras[0]["text"] if isinstance(paras[0], dict) else paras[0]
        WARNINGS.append(f"[{_CURRENT['title']}] text may overflow ({need:.2f} in needed, {h:.2f} in box): {first[:50]!r}")


def tb(s, x, y, w, h, paras, size=14, bold=False, color=INK, align="l", anchor="t", italic=False, margin=0.0):
    """Plain text box. margin=0 so the text edge sits exactly on x."""
    paras = paras if isinstance(paras, list) else [paras]
    box = s.shapes.add_textbox(E(x), E(y), E(w), E(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = E(margin)
    tf.margin_top = tf.margin_bottom = E(0)
    tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
    _fill_paras(tf, paras, size, bold, color, align, italic)
    _check(paras, w, h, size, margin, 0)
    return box


def box(s, x, y, w, h, paras="", fill="blue", edge=None, size=14, bold=False, align="c", anchor="m", shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        radius=0.12, line=1.5, color=INK, italic=False, margin=0.1, solid=None, dash=False):
    sh = s.shapes.add_shape(shape, E(x), E(y), E(w), E(h))
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        sh.adjustments[0] = min(0.5, radius / min(w, h))
    sh.shadow.inherit = False
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = solid if solid is not None else SOFT[fill]
    if edge is None and fill is not None:
        edge = fill
    if edge is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = EDGE.get(edge, EDGE["white"]) if isinstance(edge, str) else edge
        sh.line.width = Pt(line)
        if dash:
            sh.line.dash_style = MSO_LINE.DASH
    tf = sh.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = E(margin)
    tf.margin_top = tf.margin_bottom = E(0.05)
    tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
    paras = paras if isinstance(paras, list) else [paras]
    if paras and paras != [""]:
        _fill_paras(tf, paras, size, bold, color, align, italic)
        if shape in (MSO_SHAPE.ROUNDED_RECTANGLE, MSO_SHAPE.RECTANGLE):
            _check(paras, w, h, size, margin, 0.05)
    return sh


def card(s, x, y, w, h, fill, title, body, size=14, title_size=17, edge=None, bullets=True, gap=4):
    """Card with a left-aligned title and left-aligned (optionally bulleted) body — all on one left edge."""
    sh = box(s, x, y, w, h, "", fill=fill, edge=edge or fill, radius=0.14)
    pad = 0.18
    paras = [{"text": title, "size": title_size, "bold": True, "space_after": 6}]
    for b in body:
        paras.append({"text": b, "size": size, "bullet": bullets, "space_after": gap})
    tb(s, x + pad, y + 0.14, w - 2 * pad, h - 0.24, paras, size=size)
    return sh


def badge(s, cx, cy, d, text, fill=RED, size=16, color=WHITE):
    o = s.shapes.add_shape(MSO_SHAPE.OVAL, E(cx - d / 2), E(cy - d / 2), E(d), E(d))
    o.shadow.inherit = False
    o.fill.solid()
    o.fill.fore_color.rgb = fill
    o.line.fill.background()
    tf = o.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    _fill_paras(tf, [text], size, True, color, "c", False)
    return o


# ----------------------------------------------------------------------------- lines
def line(s, x1, y1, x2, y2, color=SLATE, w=1.75, arrow=True, dash=False, back_arrow=False):
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, E(x1), E(y1), E(x2), E(y2))
    c.line.color.rgb = color
    c.line.width = Pt(w)
    if dash:
        c.line.dash_style = MSO_LINE.DASH
    ln = c.line._get_or_add_ln()
    if back_arrow:
        he = etree.SubElement(ln, qn("a:headEnd"))
        he.set("type", "triangle"), he.set("w", "med"), he.set("len", "med")
    if arrow:
        te = etree.SubElement(ln, qn("a:tailEnd"))
        te.set("type", "triangle"), te.set("w", "med"), te.set("len", "med")
    return c


def path(s, pts, color=SLATE, w=1.75, dash=False):
    """Orthogonal polyline; the last segment carries the arrowhead."""
    for i in range(len(pts) - 1):
        line(s, *pts[i], *pts[i + 1], color=color, w=w, arrow=(i == len(pts) - 2), dash=dash)


def label(s, x, y, w, text, size=12, color=MUTED, align="c", bold=False, italic=False, h=0.26):
    return tb(s, x, y, w, h, text, size=size, color=color, align=align, bold=bold, italic=italic, anchor="m")


def right_arrow_big(s, x, y, w, h, fill=GREEN_D):
    a = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, E(x), E(y), E(w), E(h))
    a.shadow.inherit = False
    a.fill.solid()
    a.fill.fore_color.rgb = fill
    a.line.fill.background()
    return a


# ----------------------------------------------------------------------------- UML helpers
def actor(s, cx, top, name, color=INK, label_w=1.7):
    d = 0.34
    h = s.shapes.add_shape(MSO_SHAPE.OVAL, E(cx - d / 2), E(top), E(d), E(d))
    h.shadow.inherit = False
    h.fill.solid()
    h.fill.fore_color.rgb = WHITE
    h.line.color.rgb = color
    h.line.width = Pt(2)
    body = top + d
    line(s, cx, body, cx, body + 0.5, color=color, w=2, arrow=False)
    line(s, cx - 0.3, body + 0.17, cx + 0.3, body + 0.17, color=color, w=2, arrow=False)
    line(s, cx, body + 0.5, cx - 0.24, body + 0.88, color=color, w=2, arrow=False)
    line(s, cx, body + 0.5, cx + 0.24, body + 0.88, color=color, w=2, arrow=False)
    tb(s, cx - label_w / 2, body + 0.95, label_w, 0.5, name, size=13, bold=True, align="c")


def class_box(s, x, y, w, h, name, attrs, ops, color):
    box(s, x, y, w, h, "", fill=color, edge=color, radius=0.1)
    hd = box(s, x, y, w, 0.38, name, fill=None, edge=None, solid=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, size=14, bold=True, color=WHITE, radius=0.1)
    hd.fill.solid()
    hd.fill.fore_color.rgb = EDGE[color]
    paras = [{"text": a, "size": 12} for a in attrs]
    sep_y = y + 0.38 + 0.08 + len(attrs) * 0.2 + 0.07
    tb(s, x + 0.12, y + 0.46, w - 0.24, len(attrs) * 0.2 + 0.05, paras, size=12)
    line(s, x, sep_y, x + w, sep_y, color=EDGE[color], w=1, arrow=False)
    tb(s, x + 0.12, sep_y + 0.06, w - 0.24, h - (sep_y - y) - 0.1, [{"text": o, "size": 12, "italic": True, "color": MUTED} for o in ops], size=12)


def table_box(s, x, y, w, name, rows, color):
    """ER table: coloured header + one line per column.  rows = [(name, tag, bold)]"""
    rh = 0.25
    h = 0.4 + len(rows) * rh + 0.1
    box(s, x, y, w, h, "", fill="white", edge=color, radius=0.08)
    hd = box(s, x, y, w, 0.4, name, fill=None, edge=None, size=14, bold=True, color=WHITE, radius=0.08)
    hd.fill.solid()
    hd.fill.fore_color.rgb = EDGE[color]
    for i, (col, tag) in enumerate(rows):
        yy = y + 0.46 + i * rh
        tb(s, x + 0.12, yy, w - 0.8, rh, col, size=12, bold=tag == "PK", anchor="m")
        if tag:
            tb(s, x + w - 0.7, yy, 0.58, rh, tag, size=11, bold=True, color=EDGE[color], align="r", anchor="m")
    return h


# ----------------------------------------------------------------------------- pictures
def picture(s, path_, x, y, w, h):
    with Image.open(path_) as im:
        iw, ih = im.size
    sc = min(w / iw, h / ih)
    pw, ph = iw * sc, ih * sc
    pic = s.shapes.add_picture(str(path_), E(x + (w - pw) / 2), E(y + (h - ph) / 2), E(pw), E(ph))
    pic.line.color.rgb = EDGE["white"]
    pic.line.width = Pt(1)
    return pic


def set_current(title: str):
    _CURRENT["title"] = title
