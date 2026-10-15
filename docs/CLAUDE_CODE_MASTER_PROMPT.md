# MASTER PROMPT — paste everything below the line into Claude Code

**Before you paste (2 minutes):**
1. Create a folder, e.g. `oee-smart-factory`, and open a terminal inside it.
2. Inside it make a `docs/` folder and copy in: your final SRS `.docx`, all diagrams (use case, class, sequence, activity 1–7), your college **report template / PPT template** (if you have one) into `docs/templates/`, and your logo.
3. Run `claude`, then type `/model` and pick **Opus 5.5** for this big build (Sonnet 5.5 is fine for small follow-up fixes).
4. Paste the prompt below. Do the database yourself later using `DATABASE_MANUAL_SETUP_GUIDE.md`.

---

You are my senior full-stack engineer. Build the complete project described below **from scratch, in this folder**, until it runs end to end with one command and looks stunning. Work autonomously in milestones, run and test everything yourself, and only stop to ask me if something is truly blocked. Do not hand me half-done work.

## 0. Ground rules
- The source of truth is my SRS and diagrams in `docs/`. Read them first (convert the .docx with pandoc or python-docx; view the images). If anything below conflicts with the SRS, the SRS wins — tell me about the conflict.
- Start by writing a short plan and a task list, then execute milestone by milestone. After each milestone: run it, test it, `git commit` with a clear message.
- **I will set up the databases (PostgreSQL + InfluxDB) manually.** You must NOT start, install, or configure DB servers for me. You must make the app **fully working in real time without any database** (in-memory mode) and switch to the real databases purely through `.env` (see §5).
- Never hard-code secrets. Provide `.env.example`. No placeholder/lorem content, no fake "TODO" features. Everything on screen must be driven by live data.
- Keep code clean, typed, commented where non-obvious, with a README that a student can follow.

## 1. Project context (handoff from my previous chat)
**Title:** AI-Enhanced Real-Time OEE and Anomaly Dashboard for a Smart Factory System.
**Author:** Sanika Jamadar (B291, Batch A2), NMIMS Shirpur, Computer Engineering; guide Dr. Naziya Hussain. Subject: Software Engineering.
**What it is:** a software-only smart-factory monitor. A Python Virtual Factory Simulator generates telemetry for 5 machines every 500 ms (Temperature, Vibration, Operational Status, Cycle Count). Data flows over MQTT (Eclipse Mosquitto) into a FastAPI backend, which computes OEE, runs a rule engine, runs an ML anomaly model, projects future faults, stores data, and pushes live updates over WebSocket to a React dashboard.

## 2. Functional requirements to implement
**Simulator** — 5 machines (e.g. CNC-01, Press-02, Conveyor-03, Welder-04, Packer-05), 500 ms interval, realistic noisy signals with daily-ish drift, random micro-stops, and cycle counts. Include a **fault-injection control** (REST endpoint + dashboard button) to demo: temperature ramp, vibration spike, machine stop. Support 5–20 machines via config.

**Alert levels (4 colours):**
- 🟢 Green = normal.
- 🟡 Yellow = ML caution: Isolation Forest anomaly score > 85%.
- 🟠 Orange = What-If projected fault: fit a line `y = m·x + c` (least squares) over the last 3 minutes of temperature; if it will cross the hard threshold within the next 60 s, raise Orange with the ETA in seconds.
- 🔴 Red = rule-based hard threshold (e.g. Temperature > 85 °C, vibration above limit, or machine down). Thresholds are configurable per machine.

**OEE** = Availability × Performance × Quality, per machine and plant-wide, over rolling **1 h and 8 h** windows (selectable in UI). Define ideal cycle time and good/total counts in config; show the three factors and the product.

**ML** — scikit-learn Isolation Forest. On first start, auto-generate synthetic *normal* training data, train, save `model.pkl`, and load it at runtime. Convert the raw score to an **Anomaly Score 0–100%**. Inference must complete **< 200 ms**. Provide `python -m app.ml.train` to retrain, and log precision-style sanity metrics against injected faults.

**Maintenance & feedback** — operators can log a maintenance action against a machine/alert (who, what, when, notes), acknowledge/resolve alerts, and mark an alert as *false positive / true positive* (feedback). Write operations are protected by **HTTP Basic auth** (read endpoints open). Provide seeded demo users via env.

**API** — FastAPI, REST + WebSocket, OpenAPI at `/docs`. At minimum: `GET /health`, `GET /machines`, `GET /machines/{id}/telemetry?from&to`, `GET /oee?window=1h|8h`, `GET /alerts`, `POST /alerts/{id}/ack`, `POST /alerts/{id}/feedback`, `GET/POST /maintenance`, `POST /simulator/inject-fault`, `GET /whatif/{machine_id}`, `WS /ws/live` (broadcasts a combined snapshot every 500 ms: telemetry, anomaly score, alert state, OEE).

**Non-functional targets (measure and show them in a `/metrics`-style panel):** dashboard updates ≤ 1 s end-to-end; ML inference ≤ 200 ms; MQTT auto-reconnect ≤ 5 s (with exponential backoff, test by killing the broker); ≥ 50 concurrent WebSocket clients; retention 30 days raw / 1 year aggregated; input validation on every endpoint; structured logging.

## 3. Architecture & repo layout
```
oee-smart-factory/
  docs/                  # SRS, diagrams, templates (already here)
  simulator/             # Python virtual factory, publishes MQTT
  backend/app/           # FastAPI: api/, core/, services/ (oee, rules, whatif, alerts), ml/, storage/, ws/
  frontend/              # React + Vite + Chart.js
  db/                    # postgres_schema.sql, influx_setup.md  (for my manual DB setup)
  deploy/                # mosquitto.conf, nginx conf
  docker-compose.yml     # simulator, mosquitto, backend, frontend (DB services under profile "db", OFF by default)
  .env.example  README.md  Makefile (or run scripts for Windows too)
  report/  presentation/ # generated deliverables (see §7)
```
Follow my class diagram for domain classes and my sequence diagram for the flow (Simulator → MQTT → Backend → store → WebSocket → UI). Add a `INGEST_MODE=mqtt|direct` switch: `mqtt` is the real path; `direct` lets the simulator feed the backend in-process so the app also runs with zero Docker for quick dev.

## 4. Frontend — make it genuinely impressive
React 18 + Vite + TypeScript, **Chart.js** (react-chartjs-2) for 2D charts, a clean component structure and a single WebSocket hook with auto-reconnect and a visible connection badge.
Design direction: modern **dark industrial "control-room" theme** (with a light-mode toggle), glassmorphism cards, subtle gradients, smooth number/gauge animations, crisp typography (Inter / JetBrains Mono for numerals), consistent spacing, fully responsive (laptop, projector, phone). Colours for states must be the exact four alert colours above, with an accessible non-colour cue (icon/label).
Screens/sections:
1. **Plant overview** — big OEE gauge (A/P/Q breakdown rings), KPI cards (active machines, open alerts, avg anomaly score, throughput), 1 h / 8 h toggle.
2. **Machine grid** — 5+ live tiles: status chip, temp, vibration, cycle count, mini sparkline, anomaly score bar; click to drill in.
3. **Machine detail** — live multi-axis temperature/vibration chart with threshold line, anomaly score timeline, What-If panel showing the regression line and "projected to hit 85 °C in 42 s", per-machine OEE.
4. **Alerts centre** — live feed with colour/level filters, toasts for new alerts, ack + true/false-positive feedback, history.
5. **Maintenance** — log form + timeline, linked to alerts.
6. **Demo/Control panel** — fault-injection buttons, simulator speed, system health (latency, inference ms, WS clients, MQTT status).
Add skeleton loaders, empty states, error states, keyboard-accessible controls, and a favicon/logo. Use my logo from `docs/`. Do a visual QA pass: run the app, take screenshots with Playwright at 1440px and 390px, and fix anything ugly or misaligned before moving on.

## 5. Storage layer (the part I will wire manually)
Create a `Repository` interface with two implementations selected by `STORAGE_MODE=memory|db`:
- `memory` (default): thread-safe ring buffers for telemetry (enough for the 8 h window), in-memory alerts/maintenance/feedback. The whole app, including OEE and charts, must work in this mode.
- `db`: **InfluxDB v2** for time-series telemetry/anomaly scores/OEE (measurement `telemetry`, tags `machine_id`, fields `temperature, vibration, status, cycle_count, anomaly_score`; buckets `telemetry_raw` 30 d and `telemetry_agg` 1 y) and **PostgreSQL 14** for metadata (machines, thresholds, users, alerts, maintenance_logs, feedback, ml_models). Use SQLAlchemy + Alembic-free plain SQL schema in `db/postgres_schema.sql` (idempotent, `CREATE TABLE IF NOT EXISTS`, with indexes and seed rows for the 5 machines). Batch Influx writes (e.g. every 1 s) so the 500 ms loop never blocks. If a DB is unreachable at runtime, log it, keep serving from memory, and retry — never crash.
Env vars: `STORAGE_MODE, INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET_RAW, INFLUX_BUCKET_AGG, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD`. In Docker, DB hosts default to `host.docker.internal` (add `extra_hosts: host.docker.internal:host-gateway`) so my manually created DB containers are reachable. Add a `GET /health` that reports `storage_mode`, Influx and Postgres connectivity separately, and a startup self-check that prints a friendly message telling me exactly what is missing. Add `python -m app.storage.verify` that writes and reads back a test point/row so I can confirm my manual DB setup worked.

## 6. Quality bar & testing
- Backend tests with pytest (OEE maths, rule engine, What-If regression, anomaly scoring, auth, API contract, WebSocket smoke). Frontend: type-check + build must pass; add a few Vitest tests for the OEE/format helpers.
- Write `scripts/smoke_test.py` that starts the stack in `direct` mode, waits for data, and asserts: 5 machines streaming, OEE in 0–100 %, a Red alert appears after injecting a temperature fault, an Orange alert appears during a ramp, update latency < 1 s, inference < 200 ms.
- Run everything yourself, fix failures, and show me the actual results. Do not claim something works unless you ran it.

## 7. Deliverables beyond code
1. **Report (.docx)** in `report/` — if `docs/templates/` has my college format, follow it exactly; otherwise follow my SRS styling (Times New Roman, same cover page and colour scheme as my SRS, numbered contents starting at 1) and use this outline: Abstract, Introduction, Problem Statement, Objectives, Existing System & Limitations, Proposed System, Requirement Summary (from SRS), System Design (embed use case, class, sequence, activity diagrams + architecture diagram), Implementation (modules, key code excerpts, tech stack), Testing (test cases + real results), Results (real screenshots of the running dashboard), Conclusion, Future Scope, References. Keep it ≤ 40 pages, no filler. Update the table of contents and verify page numbers by rendering to PDF.
2. **Presentation (.pptx)** in `presentation/` — 14–16 slides using my template if present (else a clean dark/industrial theme matching the app): title, problem, objectives, architecture, tech stack, alert logic (4 colours), OEE formula, ML + What-If, UI screenshots, live-demo slide, testing/results, conclusion, future scope, Q&A. Use real screenshots captured from the running app. Add concise speaker notes.
3. **README.md** with a 5-minute quick start (with and without Docker), architecture diagram, screenshots, a demo script ("click here, inject this fault, watch Orange then Red"), and troubleshooting.

## 8. Order of work
M1 repo + simulator + Mosquitto → M2 backend ingest/validation/WebSocket (memory store) → M3 OEE + rule engine + What-If → M4 Isolation Forest service → M5 alerts/maintenance/feedback/auth → M6 React UI (all screens) + visual QA → M7 storage `db` mode + verify script (no DB servers started by you) → M8 Docker Compose + one-command run → M9 tests + smoke test → M10 README, report, PPT.

## 9. Definition of done
`docker compose up --build` (or `make dev` with no Docker) → open `http://localhost:5173` and I see five live machines updating twice a second, correct OEE, all four alert colours reachable via fault injection, the What-If panel working, alerts/maintenance/feedback working, and `/docs` showing the API. Then adding my databases per `DATABASE_MANUAL_SETUP_GUIDE.md` and setting `STORAGE_MODE=db` makes history persist with no code changes.

When finished, give me: how to run it, what I must do manually (databases only), the test results you actually observed, and any deviations from the SRS.
