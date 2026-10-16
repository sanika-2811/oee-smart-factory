"""The student's own UML / DFD diagrams (docs/uml/*.png), each on a slide with a short "how to read it" panel."""
from __future__ import annotations

from deckkit import *  # noqa: F401,F403

IMG_W, IMG_H = 7.5, 5.8
PANEL_X = X0 + IMG_W + 0.25
PANEL_W = W - IMG_W - 0.25


def build(ctx):
    new = ctx.new
    uml = ctx.root / "docs" / "uml"

    def slide(title, image, heading, points, notes, source, full=None):
        s = new(title, notes)
        if full:                                   # dense diagram: biggest possible picture, explanation as a caption underneath
            picture(s, uml / image, X0, Y0, W, 5.0, valign="t")
            tb(s, X0, Y0 + 5.15, W, 0.6, full, size=14)
            return s
        picture(s, uml / image, X0, Y0, IMG_W, IMG_H - 0.35, valign="t")
        tb(s, X0, Y1 - 0.3, IMG_W, 0.28, source, size=12, color=MUTED, italic=True)
        card(s, PANEL_X, Y0, PANEL_W, IMG_H, "grey", heading, points, size=14, title_size=17, gap=9)
        return s

    slide("UML – Use Case Diagram (SRS §7.2)", "use_case.png", "How to read it",
          ["**4 actors** and **8 use cases** from the SRS catalogue",
           "**Maintenance Engineer:** acknowledge an alarm, receive real-time alerts, log maintenance, view the dashboard",
           "**Floor Manager:** view the dashboard, trigger a What-If scenario",
           "**Production Analyst:** view historical reports",
           "**System Administrator:** deploy the system, scale simulated machines"],
          "Four actors and eight use cases from the SRS. The maintenance engineer reacts to alerts and logs maintenance; the floor manager watches the dashboard and runs What-If scenarios; "
          "the production analyst reads reports; the system administrator deploys and scales the system. Write operations need a login.",
          "Source: SRS §7.2 – use case diagram")

    slide("Data Flow Diagram – Level 1 (Seven Processes)", "dfd_level1.png", "How to read it",
          ["**P1** simulates machines and publishes telemetry to the MQTT broker (**D3**)",
           "**P2** consumes, validates and stores raw telemetry in InfluxDB (**D1**)",
           "**P3** calculates OEE; **P4** applies rules (Red); **P5** scores anomalies (Yellow)",
           "**P6** dashboard manager shows everything and sends the What-If command",
           "**P7** keeps maintenance logs and feedback in PostgreSQL (**D2**)"],
          "The context process decomposed into seven processes. P1 publishes telemetry to the MQTT broker; P2 consumes and validates it and stores it in InfluxDB; P3 computes OEE; P4 raises Red alerts "
          "from hard rules; P5 raises Yellow cautions from the ML score; P6 is the dashboard and visualisation manager; P7 handles maintenance and feedback in PostgreSQL.",
          "Source: project DFD submission (SRS §9.4)",
          full="**P1** simulate → MQTT broker **D3** → **P2** validate + store in InfluxDB **D1** → **P3** OEE · **P4** rules (Red) · **P5** ML (Yellow) → **P6** dashboard · **P7** maintenance & feedback in PostgreSQL **D2**")

    slide("UML – Class Diagram: 12 Domain Classes (SRS §8.3)", "class_diagram.png", "How to read it",
          ["**Simulator** creates 1..* **Machines**",
           "A **Machine** has 0..* **TelemetryData**, **Alerts** and **OEE** records",
           "**RuleEngine** and **MLAnomalyScorer** raise **Alerts**; **OEEEngine** produces **OEE**",
           "An **Alert** composes 0..* **MaintenanceRecords** and has 0..1 **MLAccuracyFeedback**",
           "A **User** works with maintenance records and feedback"],
          "The twelve domain classes from the SRS with their attributes and operations. Read it from the Simulator at the top right: it creates Machines; each Machine has telemetry, alerts and OEE results. "
          "The rule engine and ML scorer create Alerts, and an Alert owns its maintenance records.",
          "Source: SRS §8.3 / §9.1 – class diagram")

    slide("UML – Sequence Diagram (SRS §9.2)", "sequence.png", "How to read it",
          ["**Steps 1 – 6:** open the dashboard and log in",
           "**Steps 7 – 14:** repeat every **500 ms** – publish telemetry, validate, calculate OEE, ask the ML service for a score, save, push a live update",
           "**Steps 15 – 20:** an authenticated user acknowledges an alert and logs maintenance; the alert is marked In Progress"],
          "Six participants: User, Simulator, Backend API, ML Service, Database and Dashboard UI. Steps 1 to 6 are the login. Steps 7 to 14 repeat every 500 ms: the simulator publishes, the backend validates "
          "and calculates OEE, requests the anomaly score, saves telemetry and alerts and pushes the update to the dashboard. Steps 15 to 20 are the authenticated write operations.",
          "Source: SRS §9.2 – sequence diagram")
