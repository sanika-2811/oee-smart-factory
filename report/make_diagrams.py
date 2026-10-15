"""Draw the design diagrams used in the report and presentation (matplotlib, print-friendly).

    python report/make_diagrams.py        # writes report/figures/*.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, FancyArrowPatch, FancyBboxPatch, Polygon

OUT = Path(__file__).parent / "figures"
OUT.mkdir(exist_ok=True)
INK, MUTED, LINE = "#0f172a", "#475569", "#94a3b8"
C = {"blue": "#dbeafe", "cyan": "#cffafe", "green": "#dcfce7", "yellow": "#fef9c3", "orange": "#ffedd5", "red": "#fee2e2",
     "violet": "#ede9fe", "grey": "#f1f5f9"}
EDGE = {"blue": "#2563eb", "cyan": "#0891b2", "green": "#16a34a", "yellow": "#ca8a04", "orange": "#ea580c", "red": "#dc2626",
        "violet": "#7c3aed", "grey": "#64748b"}


def canvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h), dpi=200)
    ax.set_xlim(0, w * 10), ax.set_ylim(0, h * 10), ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, text, color="blue", fs=9, bold=False, align="center"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.2,rounding_size=1.2", fc=C[color], ec=EDGE[color], lw=1.4))
    ax.text(x + (w / 2 if align == "center" else 1.5), y + h / 2, text, ha=align, va="center", fontsize=fs, color=INK,
            fontweight="bold" if bold else "normal", linespacing=1.35)


def arrow(ax, p, q, text="", color=MUTED, style="-|>", dashed=False, fs=7.5, off=(0, 1.2), rad=0.0):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=11, lw=1.3, color=color, ls="--" if dashed else "-",
                                 connectionstyle=f"arc3,rad={rad}"))
    if text:
        ax.text((p[0] + q[0]) / 2 + off[0], (p[1] + q[1]) / 2 + off[1], text, ha="center", va="bottom", fontsize=fs, color=MUTED)


def save(fig, name):
    fig.savefig(OUT / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", OUT / name)


# --------------------------------------------------------------------------- architecture
def architecture():
    fig, ax = canvas(16, 9.2)
    ax.text(80, 89, "System architecture - AI-Enhanced Real-Time OEE & Anomaly Dashboard", ha="center", fontsize=12, fontweight="bold", color=INK)
    box(ax, 4, 52, 24, 20, "Virtual Factory\nSimulator\n(Python)\n5-20 machines\nevery 500 ms", "violet", 9, True)
    box(ax, 38, 52, 22, 20, "Eclipse Mosquitto\nMQTT broker\nTCP :1883\nWebSocket :9001", "orange", 9, True)
    arrow(ax, (28.5, 62), (37.5, 62), "MQTT / WS\nfactory/telemetry/#", EDGE["violet"], off=(0, 1.5))
    arrow(ax, (37.5, 56), (28.5, 56), "factory/control", EDGE["orange"], off=(0, -3.5), dashed=True)
    # backend container
    ax.add_patch(FancyBboxPatch((66, 30), 88, 52, boxstyle="round,pad=0.2,rounding_size=1.5", fc="#f8fafc", ec=EDGE["blue"], lw=1.6, ls="--"))
    ax.text(110, 79, "FastAPI backend (asyncio)", ha="center", fontsize=10, fontweight="bold", color=EDGE["blue"])
    box(ax, 69, 60, 25, 14, "Ingest + validation\n(Pydantic, FR-09)", "blue", 8.5)
    box(ax, 97, 60, 25, 14, "OEE engine\nA x P x Q  (1 h / 8 h)", "green", 8.5)
    box(ax, 125, 60, 26, 14, "Rule engine\nhard limits -> RED", "red", 8.5)
    box(ax, 69, 41, 25, 14, "Isolation Forest\nscorer -> YELLOW (>85 %)", "yellow", 8.5)
    box(ax, 97, 41, 25, 14, "What-If projection\ny = m x + c -> ORANGE", "orange", 8.5)
    box(ax, 125, 41, 26, 14, "Alert manager\nack / resolve / feedback", "violet", 8.5)
    box(ax, 69, 32, 82, 6, "REST API + OpenAPI /docs  |  HTTP Basic auth  |  WebSocket /ws/live (500 ms snapshot)", "grey", 8.2)
    arrow(ax, (60.5, 62), (68.5, 66), "subscribe", MUTED)
    # stores
    box(ax, 68, 6, 36, 16, "InfluxDB v2\ntelemetry_raw (30 d)\ntelemetry_agg (1 y)", "cyan", 8.5, True)
    box(ax, 112, 6, 36, 16, "PostgreSQL 14\nmachines, users, alerts,\nmaintenance, feedback", "cyan", 8.5, True)
    arrow(ax, (86, 29.5), (86, 22.5), "time series", MUTED, off=(8, 0))
    arrow(ax, (130, 29.5), (130, 22.5), "metadata", MUTED, off=(8, 0))
    # frontend
    box(ax, 4, 14, 52, 24, "React 18 + Vite dashboard\nChart.js 2D charts\nOverview | Machines | Alerts\nMaintenance | Reports | Control", "green", 9, True)
    arrow(ax, (65.5, 40), (56.5, 30), "REST + WebSocket\n(via nginx /api)", EDGE["green"], off=(-1, 2))
    ax.text(30, 8, "Browser (Chrome / Edge / Firefox)", ha="center", fontsize=8.5, color=MUTED)
    ax.text(110, 1.5, "STORAGE_MODE=memory runs with no database; STORAGE_MODE=db adds InfluxDB + PostgreSQL", ha="center", fontsize=7.5, color=MUTED, style="italic")
    save(fig, "architecture.png")


# --------------------------------------------------------------------------- use case
def usecase():
    fig, ax = canvas(16, 9.5)
    ax.add_patch(FancyBboxPatch((36, 3), 102, 88, boxstyle="round,pad=0.2,rounding_size=1.5", fc="#f8fafc", ec=LINE, lw=1.3))
    ax.text(87, 92.5, "Smart Factory Dashboard", ha="center", fontsize=11, fontweight="bold", color=INK)
    cases = [("UC-1 View real-time dashboard", 76, 84), ("UC-2 View machine telemetry", 76, 74.5), ("UC-3 Receive real-time alerts", 76, 65),
             ("UC-4 Acknowledge an alarm", 76, 55.5), ("UC-5 Log maintenance activity", 76, 46), ("UC-6 Provide ML feedback", 76, 36.5),
             ("UC-7 Trigger What-If scenario", 76, 27), ("UC-8 View projected degradation", 76, 17.5), ("UC-9 View historical reports", 118, 76),
             ("UC-15 Scale simulated machines", 118, 36), ("UC-14 Deploy system", 118, 24), ("UC-17 Authenticate user", 118, 56)]
    pos = {}
    for t, x, y in cases:
        ax.add_patch(Ellipse((x, y), 32 if x < 90 else 28, 7.4, fc=C["blue"], ec=EDGE["blue"], lw=1.2))
        ax.text(x, y, t, ha="center", va="center", fontsize=7.4, color=INK)
        pos[t.split()[0]] = (x, y)
    actors = {"Floor Manager": (12, 72), "Maintenance Engineer": (12, 44), "Production Analyst": (150, 76), "System Administrator": (150, 30)}
    for name, (x, y) in actors.items():
        ax.add_patch(plt.Circle((x, y + 6), 2.2, fc="white", ec=INK, lw=1.3))
        ax.plot([x, x], [y + 3.8, y - 3], color=INK, lw=1.3), ax.plot([x - 3.5, x + 3.5], [y + 1.5, y + 1.5], color=INK, lw=1.3)
        ax.plot([x, x - 3], [y - 3, y - 8], color=INK, lw=1.3), ax.plot([x, x + 3], [y - 3, y - 8], color=INK, lw=1.3)
        ax.text(x, y - 11, name, ha="center", fontsize=8, fontweight="bold", color=INK)
    links = {"Floor Manager": ["UC-1", "UC-2", "UC-7", "UC-8"], "Maintenance Engineer": ["UC-3", "UC-4", "UC-5", "UC-6", "UC-2"],
             "Production Analyst": ["UC-9", "UC-1"], "System Administrator": ["UC-14", "UC-15"]}
    for a, ucs in links.items():
        ax_, ay_ = actors[a]
        for u in ucs:
            ux, uy = pos[u]
            sx = ax_ + (4 if ax_ < 76 else -4)
            ex = ux - (16 if ax_ < 76 else -14) if ux < 90 or ax_ < 76 else ux + 14
            ax.plot([sx, ex], [ay_ + 1, uy], color=LINE, lw=0.9)
    for u in ("UC-4", "UC-5", "UC-7", "UC-15"):   # <<include>> authentication
        ux, uy = pos[u]
        arrow(ax, (ux + 16, uy), (104, 56) if u != "UC-15" else (118, 52.4), "", EDGE["grey"], dashed=True)
    ax.text(96, 59.5, "<<include>>", fontsize=7, color=MUTED, style="italic")
    save(fig, "usecase.png")


# --------------------------------------------------------------------------- class diagram
def classes():
    fig, ax = canvas(18.4, 11.2)
    defs = {
        "Simulator": (3, 74, "blue", ["machines: Machine[1..*]", "interval_ms = 500"], ["step()", "injectFault()", "publish()"]),
        "Machine": (38, 74, "blue", ["id, name, kind", "tempLimit, vibLimit", "idealCycleS"], ["thresholds()"]),
        "TelemetryData": (74, 74, "green", ["machineId, ts", "temperature, vibration", "status, cycleCount"], ["validate()"]),
        "OEEEngine": (108, 74, "green", ["windows: 1h, 8h"], ["update(sample)", "result(window)"]),
        "OEE": (142, 74, "green", ["availability, performance", "quality, oee"], ["compute()"]),
        "RuleEngine": (38, 38, "red", ["tempLimit, vibLimit"], ["evaluate(sample): Condition[]"]),
        "MLAnomalyScorer": (38, 4, "yellow", ["model.pkl (IsolationForest)", "threshold = 85 %"], ["score(batch): 0-100 %"]),
        "Alert": (74, 38, "orange", ["id, level, kind, status", "openedAt, clearedAt", "eta, score, feedback"], ["acknowledge()", "resolve()"]),
        "MaintenanceRecord": (108, 38, "violet", ["id, action, notes", "technician, status"], ["close()"]),
        "MLAccuracyFeedback": (142, 38, "violet", ["verdict (TP / FP)", "givenBy, comment"], ["precision()"]),
        "User": (74, 4, "grey", ["username, role", "passwordHash"], ["authenticate()"]),
        "DashboardConfig": (3, 4, "grey", ["window (1h / 8h)", "theme, machineCount"], ["apply()"]),
    }
    pos = {}
    for name, (x, y, col, attrs, ops) in defs.items():
        w, h = 30, 26
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1,rounding_size=0.8", fc=C[col], ec=EDGE[col], lw=1.4))
        ax.plot([x, x + w], [y + h - 6, y + h - 6], color=EDGE[col], lw=1), ax.plot([x, x + w], [y + 8.5, y + 8.5], color=EDGE[col], lw=0.8)
        ax.text(x + w / 2, y + h - 3, name, ha="center", va="center", fontsize=8.6, fontweight="bold", color=INK)
        ax.text(x + 1.2, y + h - 8, "\n".join(attrs), ha="left", va="top", fontsize=6.6, color=INK, linespacing=1.4)
        ax.text(x + 1.2, y + 7.4, "\n".join(ops), ha="left", va="top", fontsize=6.6, color=MUTED, linespacing=1.4)
        pos[name] = (x, y, w, h)

    def link(a, b, label, style="-|>", dashed=False, rad=0.0):
        xa, ya, wa, ha = pos[a]
        xb, yb, wb, hb = pos[b]
        pa = (xa + wa, ya + ha / 2) if xb > xa + wa - 1 else (xa + wa / 2, ya) if yb < ya else (xa + wa / 2, ya + ha)
        pb = (xb, yb + hb / 2) if xb > xa + wa - 1 else (xb + wb / 2, yb + hb) if yb < ya else (xb + wb / 2, yb)
        arrow(ax, pa, pb, label, EDGE["grey"], style=style, dashed=dashed, fs=6.5, off=(0, 0.8), rad=rad)

    link("Simulator", "Machine", "1 .. *", "-|>")
    link("Machine", "TelemetryData", "0 .. *", "-|>")
    link("OEEEngine", "OEE", "creates", "-|>", True)
    link("TelemetryData", "OEEEngine", "feeds", "-|>", True)
    link("Machine", "Alert", "0 .. *", "-|>", rad=0.0)
    link("RuleEngine", "Alert", "raises", "-|>", True)
    link("MLAnomalyScorer", "Alert", "raises", "-|>", True)
    link("Alert", "MaintenanceRecord", "composes 0 .. *", "-|>")
    link("MaintenanceRecord", "MLAccuracyFeedback", "", "-|>", True)
    link("User", "MaintenanceRecord", "0 .. *", "-|>", rad=-0.1)
    ax.text(92, 107, "Class diagram - 12 domain classes (SRS section 7.3)", ha="center", fontsize=11, fontweight="bold", color=INK)
    save(fig, "class_diagram.png")


# --------------------------------------------------------------------------- sequence
def sequence():
    fig, ax = canvas(16, 10.2)
    actors = ["Simulator", "Mosquitto", "FastAPI\nengine", "Isolation\nForest", "Storage\n(Influx/PG)", "React\ndashboard"]
    xs = [12, 40, 68, 96, 124, 150]
    for a, x in zip(actors, xs):
        box(ax, x - 10, 92, 20, 7, a, "blue", 8, True)
        ax.plot([x, x], [90, 4], color=LINE, lw=1, ls="--")
    steps = [
        (0, 1, 86, "publish factory/telemetry/CNC-01 (500 ms)", False),
        (1, 2, 80, "deliver message (MQTT over WebSockets)", False),
        (2, 2, 74, "validate payload (FR-09), update OEE windows, evaluate rules", True),
        (2, 3, 66, "score batch of features (<= 200 ms)", False),
        (3, 2, 61, "anomaly score 0-100 %", False),
        (2, 2, 55, "What-If regression y = m x + c, alert state machine", True),
        (2, 4, 48, "queue batched write (about 1 s) / save alert", False),
        (2, 5, 41, "WebSocket snapshot every 500 ms (colours, OEE, scores)", False),
        (5, 2, 34, "POST /alerts/{id}/ack (HTTP Basic)", False),
        (2, 4, 27, "persist acknowledgement + feedback", False),
        (2, 5, 20, "alert_event pushed to all clients", False),
        (5, 2, 13, "POST /simulator/inject-fault", False),
        (2, 1, 8, "publish factory/control {inject}", False),
        (1, 0, 5, "deliver command -> fault profile starts", False),
    ]
    for a, b, y, text, selfcall in steps:
        xa, xb = xs[a], xs[b]
        if selfcall:
            ax.add_patch(FancyBboxPatch((xa - 14, y - 3.4), 40, 6.8, boxstyle="round,pad=0.1", fc=C["yellow"], ec=EDGE["yellow"], lw=1))
            ax.text(xa + 6, y, text, ha="center", va="center", fontsize=6.2, color=INK, wrap=True)
        else:
            arrow(ax, (xa, y), (xb, y), "", EDGE["blue"] if xb > xa else EDGE["green"])
            ax.text((xa + xb) / 2, y + 1.2, text, ha="center", fontsize=6.6, color=INK)
    ax.text(80, 103, "Sequence diagram - real-time ingestion, alerting and operator actions", ha="center", fontsize=11, fontweight="bold", color=INK)
    save(fig, "sequence.png")


# --------------------------------------------------------------------------- alert flow
def flowchart():
    fig, ax = canvas(15, 10)

    def diamond(x, y, w, h, text):
        ax.add_patch(Polygon([(x, y + h / 2), (x + w / 2, y + h), (x + w, y + h / 2), (x + w / 2, y)], fc=C["grey"], ec=EDGE["grey"], lw=1.3))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=7.6, color=INK)

    ax.text(70, 97, "Alert decision flow (every 500 ms per machine)", ha="center", fontsize=11, fontweight="bold", color=INK)
    box(ax, 50, 86, 40, 7, "Telemetry sample received and validated", "blue", 8.5)
    diamond(45, 70, 50, 12, "Temperature > limit, vibration > limit\nor status = STOPPED ?")
    box(ax, 100, 72, 34, 8, "RED  hard fault\n(rule engine, immediate)", "red", 8.5, True)
    diamond(45, 52, 50, 12, "Regression line reaches the limit\nwithin 60 s ?  (R2 >= 0.6, slope > 0.03 C/s)")
    box(ax, 100, 54, 34, 8, "ORANGE  projected fault\nwith ETA countdown", "orange", 8.5, True)
    diamond(45, 34, 50, 12, "Isolation Forest anomaly score\n> 85 % for 2 consecutive ticks ?")
    box(ax, 100, 36, 34, 8, "YELLOW  ML caution", "yellow", 8.5, True)
    box(ax, 50, 17, 40, 8, "GREEN  normal operation", "green", 8.5, True)
    arrow(ax, (70, 86), (70, 82.5)); arrow(ax, (70, 70), (70, 64.5), "no", off=(3, 0)); arrow(ax, (70, 52), (70, 46.5), "no", off=(3, 0))
    arrow(ax, (70, 34), (70, 25.5), "no", off=(3, 0))
    arrow(ax, (95, 76), (99.5, 76), "yes", off=(0, 1)); arrow(ax, (95, 58), (99.5, 58), "yes", off=(0, 1)); arrow(ax, (95, 40), (99.5, 40), "yes", off=(0, 1))
    box(ax, 100, 14, 34, 9, "Alert manager -> operator:\nacknowledge, assign, resolve,\ntrue / false positive feedback", "violet", 7.6)
    for y in (76, 58, 40):
        arrow(ax, (134.5, y), (138, y), "", LINE, dashed=True)
    ax.plot([138, 138], [76, 18.5], color=LINE, lw=1.3, ls="--")
    arrow(ax, (138, 18.5), (134.5, 18.5), "", LINE, dashed=True)
    ax.text(70, 8, "Higher levels suppress lower ones; each alert clears after its condition is absent for 3-4 s", ha="center", fontsize=7.8, color=MUTED, style="italic")
    save(fig, "alert_flow.png")


# --------------------------------------------------------------------------- ER
def erd():
    fig, ax = canvas(15, 8)
    tabs = {
        "machines": (4, 52, ["id PK", "name, kind", "ideal_cycle_s", "temp_limit, vib_limit"], "blue"),
        "users": (4, 14, ["username PK", "role", "password_hash"], "grey"),
        "alerts": (52, 40, ["id PK", "machine_id FK", "level, kind, status", "opened_at, cleared_at", "acked_by, technician", "resolved_by, notes", "payload JSONB"], "orange"),
        "feedback": (100, 54, ["id PK", "alert_id FK UNIQUE", "verdict (TP / FP)", "given_by, comment"], "yellow"),
        "maintenance_logs": (100, 14, ["id PK", "machine_id FK", "alert_id FK", "action, notes", "technician, status", "created_by"], "violet"),
        "ml_models": (52, 6, ["id PK", "algorithm", "trained_at", "metrics JSONB"], "green"),
    }
    pos = {}
    for n, (x, y, rows, col) in tabs.items():
        h = 8 + 5.2 * len(rows)
        ax.add_patch(FancyBboxPatch((x, y), 40, h, boxstyle="round,pad=0.1,rounding_size=0.8", fc=C[col], ec=EDGE[col], lw=1.4))
        ax.plot([x, x + 40], [y + h - 7, y + h - 7], color=EDGE[col], lw=1)
        ax.text(x + 20, y + h - 3.6, n, ha="center", va="center", fontsize=9, fontweight="bold", color=INK)
        ax.text(x + 2, y + h - 9, "\n".join(rows), ha="left", va="top", fontsize=7.4, color=INK, linespacing=1.55)
        pos[n] = (x, y, 40, h)
    arrow(ax, (44.5, 66), (51.5, 62), "1 : N", EDGE["grey"], style="-|>")
    arrow(ax, (92, 62), (99.5, 64), "1 : 0..1", EDGE["grey"], style="-|>")
    arrow(ax, (92, 50), (99.5, 40), "1 : N", EDGE["grey"], style="-|>")
    arrow(ax, (44.5, 56), (99.5, 32), "1 : N", EDGE["grey"], style="-|>", rad=-0.25)
    ax.text(75, 79, "PostgreSQL schema (db/postgres_schema.sql)", ha="center", fontsize=11, fontweight="bold", color=INK)
    ax.text(25, 4, "Time series (telemetry, anomaly scores, hourly OEE) live in InfluxDB v2", ha="left", fontsize=7.6, color=MUTED, style="italic")
    save(fig, "er_diagram.png")


if __name__ == "__main__":
    for f in (architecture, usecase, classes, sequence, flowchart, erd):
        f()
