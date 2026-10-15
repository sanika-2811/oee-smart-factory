# Database setup — step by step (with checkpoints)

You do this part; I (Claude) cannot reach your machine's databases. Do the steps in order. **After every step there is a ✅ checkpoint** — if it does not look like the description, stop and send me the exact text you see.

> **Important:** Docker is **not installed** on this computer (the command `docker` was not found). Choose **one** path:
> * **Path A – Docker Desktop** (matches your `DATABASE_MANUAL_SETUP_GUIDE.md`; ~15 min incl. restart)
> * **Path B – Install the two databases natively on Windows** (no Docker; ~25 min)

The app already works without any database (`STORAGE_MODE=memory`). Everything below only adds persistence. You can stop at any time and keep using memory mode.

---
## Step 0 – Pick values and write them down
Use these (or your own; they must match everywhere):

| Item | Value |
|---|---|
| Postgres user / password / database | `oee_user` / `ChangeMe123` / `oee_db` |
| Influx org / bucket | `oee-org` / `telemetry_raw` (30 d) and `telemetry_agg` (365 d) |
| Influx admin user / password | `admin` / `ChangeMe12345` (min 8 chars) |
| Influx API token | `oee-super-secret-token` (change it to something of your own) |

---
## PATH A — Docker Desktop

**A1. Install Docker Desktop.** Download from docker.com → install → restart if asked (accept WSL 2 if it offers).
✅ Open **PowerShell** and run `docker --version` → prints a version. Then `docker ps` → prints a header row (no error). *If "engine not running": open Docker Desktop and wait for "Engine running".*

**A2. Start PostgreSQL 14** (one line):
```powershell
docker run -d --name oee-postgres -e POSTGRES_USER=oee_user -e POSTGRES_PASSWORD=ChangeMe123 -e POSTGRES_DB=oee_db -p 5432:5432 -v oee_pgdata:/var/lib/postgresql/data postgres:14
```
✅ `docker ps` lists `oee-postgres` with status `Up`.

**A3. Create the tables** (run from the project folder `SE_Project`):
```powershell
docker cp db\postgres_schema.sql oee-postgres:/schema.sql
docker exec -it oee-postgres psql -U oee_user -d oee_db -f /schema.sql
```
✅ You see lines like `CREATE TABLE`, `CREATE INDEX`, `INSERT 0 5` and **no** `ERROR`.
```powershell
docker exec -it oee-postgres psql -U oee_user -d oee_db -c "SELECT id, name FROM machines;"
```
✅ Five rows: CNC-01, Press-02, Conveyor-03, Welder-04, Packer-05.

**A4. Start InfluxDB 2.7** (one line):
```powershell
docker run -d --name oee-influx -p 8086:8086 -v oee_influxdata:/var/lib/influxdb2 -e DOCKER_INFLUXDB_INIT_MODE=setup -e DOCKER_INFLUXDB_INIT_USERNAME=admin -e DOCKER_INFLUXDB_INIT_PASSWORD=ChangeMe12345 -e DOCKER_INFLUXDB_INIT_ORG=oee-org -e DOCKER_INFLUXDB_INIT_BUCKET=telemetry_raw -e DOCKER_INFLUXDB_INIT_RETENTION=30d -e DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=oee-super-secret-token influxdb:2.7
```
✅ Open <http://localhost:8086> → login page → sign in `admin` / `ChangeMe12345` → left menu **Load Data → Buckets** shows `telemetry_raw`.

**A5. Create the 1-year bucket:**
```powershell
docker exec oee-influx influx bucket create -n telemetry_agg -o oee-org -r 365d -t oee-super-secret-token
```
✅ Prints a table with `telemetry_agg`. (Or UI: Buckets → Create Bucket → name `telemetry_agg`, delete data older than 365 days.)

Go to **Step 6**.

---
## PATH B — native Windows install (no Docker)

**B1. PostgreSQL.** Download the Windows installer for **PostgreSQL 14** (or newer 14–16) from postgresql.org/download/windows → run it. Set the `postgres` superuser password (remember it!), keep port **5432**, install **pgAdmin/Command Line Tools**.
✅ Start menu has **SQL Shell (psql)**.

**B2. Create the user and database.** Open **SQL Shell (psql)**, press Enter through the prompts (server localhost, database postgres, port 5432, user postgres), type the postgres password, then run:
```sql
CREATE USER oee_user WITH PASSWORD 'ChangeMe123';
CREATE DATABASE oee_db OWNER oee_user;
\q
```
✅ Output `CREATE ROLE` and `CREATE DATABASE`.

**B3. Create the tables.** In a normal PowerShell, from the project folder (adjust the path if your PostgreSQL version differs):
```powershell
& "C:\Program Files\PostgreSQL\14\bin\psql.exe" -U oee_user -d oee_db -h localhost -f db\postgres_schema.sql
```
(enter `ChangeMe123`)
✅ `CREATE TABLE…`, `INSERT 0 5`, no `ERROR`.

**B4. InfluxDB.** Download **InfluxDB 2.x for Windows (amd64)** from influxdata.com/downloads (a .zip), unzip it to `C:\influxdb`, then run (leave this window open):
```powershell
cd C:\influxdb
.\influxd.exe
```
✅ Log lines appear and finally `Listening ... port=8086`.

**B5. First-time setup.** Open <http://localhost:8086> → **Get Started** → username `admin`, password `ChangeMe12345`, organization `oee-org`, initial bucket `telemetry_raw` → **Configure later**/continue.
Then **Load Data → Buckets → telemetry_raw → Settings → Delete data: older than 30 days**.
Then **Create Bucket** → `telemetry_agg` → older than **365 days**.
Then **Load Data → API Tokens → Generate API Token → All Access Token** → copy the token (you will paste it into `.env`). *(Skip the manual token if you used the Docker command — the token is `oee-super-secret-token`.)*
✅ Buckets page shows both buckets with 30 d and 365 d retention.

---
## Step 6 – (both paths) hourly down-sampling task
In Influx UI: **Tasks → Create Task → New Task**, name `downsample_telemetry_1h`, paste:
```flux
option task = {name: "downsample_telemetry_1h", every: 1h}

from(bucket: "telemetry_raw")
  |> range(start: -task.every)
  |> filter(fn: (r) => r._measurement == "telemetry")
  |> filter(fn: (r) => r._field == "temperature" or r._field == "vibration" or r._field == "anomaly_score")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> to(bucket: "telemetry_agg", org: "oee-org")
```
→ **Save**. ✅ The task appears in the Tasks list as *Active*.

## Step 7 – tell the app about the databases
In the project folder: copy `.env.example` to `.env` (if you have not) and set exactly:
```ini
STORAGE_MODE=db
INFLUX_URL=http://localhost:8086
INFLUX_TOKEN=oee-super-secret-token        # or the token you generated in B5
INFLUX_ORG=oee-org
INFLUX_BUCKET_RAW=telemetry_raw
INFLUX_BUCKET_AGG=telemetry_agg
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=oee_db
POSTGRES_USER=oee_user
POSTGRES_PASSWORD=ChangeMe123
```

## Step 8 – verify (this is the real test)
```powershell
cd backend
& "$env:USERPROFILE\.venvs\oee\Scripts\python.exe" -m app.storage.verify
```
✅ You must see **`[OK]`** lines for: PostgreSQL connected · all 6 tables exist · machines has 5 rows · test row written/read; InfluxDB reachable · both buckets exist · test point written and read back; and finally *"Both databases are ready"*.
If you see `[FAIL]`, copy the full output to me — the messages say exactly what is missing.

## Step 9 – run the app and prove persistence
1. Start the app (`scripts\dev.ps1`). In the backend window you should see `storage: PostgreSQL ok, InfluxDB ok`.
2. Open <http://localhost:8000/health> → `"storage_mode":"db","influx":"ok","postgres":"ok"`. The **Control** page shows the same.
3. Sign in → **Control** → inject a fault (e.g. *Vibration spike*) → in **Alerts** acknowledge it and give feedback.
4. Wait ~1 minute. In Influx UI: **Data Explorer → telemetry_raw → telemetry → temperature** → Submit → you see live points. In Postgres:
   * Docker: `docker exec -it oee-postgres psql -U oee_user -d oee_db -c "SELECT id, machine_id, level, status FROM alerts ORDER BY id DESC LIMIT 5;"`
   * Native: run the same `SELECT` with `psql.exe` (see B3).
5. **Restart the backend** (Ctrl+C, start again). ✅ Your acknowledged alert and the maintenance records are **still there** in the Alerts / Maintenance pages. That is persistence working.
6. **Outage test (optional):** stop the Postgres container (`docker stop oee-postgres`) or the Windows service. ✅ The dashboard keeps updating, `/health` shows `"postgres":"unreachable"`; start it again and it recovers within ~30 s with no restart.

## Troubleshooting
| Message | Fix |
|---|---|
| `password authentication failed` | `.env` password ≠ the one used when the database was first created. (Docker: the password is fixed at first creation — remove the volume to change it.) |
| `connection refused` | The database is not running / wrong port. `docker ps`, or check the Windows service "postgresql-x64-14". |
| `unauthorized` from Influx | `INFLUX_TOKEN` or `INFLUX_ORG` wrong — they must match exactly. |
| `bucket 'telemetry_agg' not found` | Do A5 / B5 (create the second bucket). |
| Port 5432 or 8086 already in use | Another Postgres/Influx is running. Stop it, or map another host port and change `.env`. |
| Everything is fine but nothing persists | `STORAGE_MODE` is still `memory` — edit `.env` and restart the backend. |

**Safe fallback:** set `STORAGE_MODE=memory` any time.

## For the viva
*"Time-series telemetry is written to InfluxDB v2 (30-day raw bucket, 1-year aggregated bucket); relational metadata — machines, users, alerts, maintenance logs and operator feedback — lives in PostgreSQL 14. Writes are queued and batched so the 500 ms real-time loop never blocks, and if a database goes down the dashboard keeps running from memory and reconnects automatically."*

## What I have and have not verified (honest status)
* ✅ Schema and every SQL statement parse with the PostgreSQL grammar; repository queue / retry / batching logic is unit-tested against fake clients (7 tests); the "database unreachable" behaviour was tested for real.
* ❌ Not tested against live InfluxDB / PostgreSQL servers — **Step 8 and Step 9 are that test.** Send me the output and I will fix anything that fails.
