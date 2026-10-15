# Database Manual Setup Guide — OEE Smart Factory Dashboard

You will set up **two databases** yourself. Your app already works without them (`STORAGE_MODE=memory`); doing this makes data **persist** and fulfils the SRS (InfluxDB for time-series, PostgreSQL for metadata).

| Database | Stores | Port |
|---|---|---|
| PostgreSQL 14 | machines, thresholds, users, alerts, maintenance logs, feedback, ML model info | 5432 |
| InfluxDB 2.x | telemetry (temperature, vibration, status, cycles), anomaly scores, OEE | 8086 |

Easiest path = **Docker Desktop** (Part 1). Everything below uses it. Use PowerShell on Windows, Terminal on Mac/Linux.

---

## Part 1 — Install Docker Desktop
1. Download from docker.com → Docker Desktop. Install, restart if asked.
2. Open Docker Desktop and wait until it says **Engine running**.
3. Check in a terminal: `docker --version` and `docker ps` (should print a header, no error).

> Windows: if it asks for WSL 2, accept the install, then reboot.

## Part 2 — PostgreSQL 14

**Step 1 — start the container** (one line; change the password):
```
docker run -d --name oee-postgres -e POSTGRES_USER=oee_user -e POSTGRES_PASSWORD=ChangeMe123 -e POSTGRES_DB=oee_db -p 5432:5432 -v oee_pgdata:/var/lib/postgresql/data postgres:14
```
The `-v oee_pgdata` part keeps your data even if the container is deleted.

**Step 2 — check it is running:** `docker ps` should list `oee-postgres`. If not: `docker logs oee-postgres`.

**Step 3 — create the tables.** Claude Code generated `db/postgres_schema.sql` for you. Copy it in and run it:
```
docker cp db/postgres_schema.sql oee-postgres:/schema.sql
docker exec -it oee-postgres psql -U oee_user -d oee_db -f /schema.sql
```
You should see a list of `CREATE TABLE` / `INSERT` lines and no `ERROR`. (Safe to run twice — it uses `IF NOT EXISTS`.)

**Step 4 — verify:**
```
docker exec -it oee-postgres psql -U oee_user -d oee_db -c "\dt"
docker exec -it oee-postgres psql -U oee_user -d oee_db -c "SELECT * FROM machines;"
```
`\dt` lists your tables; `machines` should show the 5 seeded machines.

**Optional GUI:** install DBeaver or pgAdmin → new PostgreSQL connection → host `localhost`, port `5432`, database `oee_db`, user `oee_user`, your password.

## Part 3 — InfluxDB 2.x

**Step 1 — start the container** (it self-configures on first boot):
```
docker run -d --name oee-influx -p 8086:8086 -v oee_influxdata:/var/lib/influxdb2 -e DOCKER_INFLUXDB_INIT_MODE=setup -e DOCKER_INFLUXDB_INIT_USERNAME=admin -e DOCKER_INFLUXDB_INIT_PASSWORD=ChangeMe12345 -e DOCKER_INFLUXDB_INIT_ORG=oee-org -e DOCKER_INFLUXDB_INIT_BUCKET=telemetry_raw -e DOCKER_INFLUXDB_INIT_RETENTION=30d -e DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=oee-super-secret-token influxdb:2.7
```
This creates: user `admin`, organisation `oee-org`, bucket `telemetry_raw` that **keeps data 30 days** (SRS: 30 days raw), and your API token `oee-super-secret-token` (change it to something of your own and remember it).
Password must be 8+ characters.

**Step 2 — open the UI:** go to http://localhost:8086 and log in with `admin` / your password. (You will see an empty bucket until the app writes data.)

**Step 3 — create the 1-year aggregated bucket** (SRS: 1 year aggregated):
- UI way: left menu → **Load Data → Buckets → Create Bucket** → name `telemetry_agg` → Delete Data: **Older than 365 days** → Create.
- Or command line:
```
docker exec oee-influx influx bucket create -n telemetry_agg -o oee-org -r 365d -t oee-super-secret-token
```

**Step 4 — add the hourly downsampling task** so the long-term bucket fills automatically:
- UI: **Tasks → Create Task → New Task**, name `downsample_telemetry_1h`, paste:
```
option task = {name: "downsample_telemetry_1h", every: 1h}

from(bucket: "telemetry_raw")
  |> range(start: -task.every)
  |> filter(fn: (r) => r._measurement == "telemetry")
  |> filter(fn: (r) => r._field == "temperature" or r._field == "vibration" or r._field == "anomaly_score")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> to(bucket: "telemetry_agg", org: "oee-org")
```
  then **Save**.

**Step 5 — test write + read** (proves token, org and buckets are right):
```
docker exec oee-influx influx write -b telemetry_raw -o oee-org -t oee-super-secret-token "telemetry,machine_id=TEST temperature=71.2,vibration=2.1"
docker exec oee-influx influx query -o oee-org -t oee-super-secret-token "from(bucket:\"telemetry_raw\") |> range(start: -10m) |> filter(fn:(r)=>r.machine_id==\"TEST\")"
```
You should see rows for `temperature` and `vibration`. (On Windows PowerShell, if the quotes complain, run the query from the UI: **Data Explorer → Script Editor**.)

## Part 4 — Connect the app
1. In the project root copy `.env.example` to `.env` and fill in:
```
STORAGE_MODE=db

INFLUX_URL=http://localhost:8086
INFLUX_TOKEN=oee-super-secret-token
INFLUX_ORG=oee-org
INFLUX_BUCKET_RAW=telemetry_raw
INFLUX_BUCKET_AGG=telemetry_agg

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=oee_db
POSTGRES_USER=oee_user
POSTGRES_PASSWORD=ChangeMe123
```
2. Running the backend **inside Docker Compose**? Use `host.docker.internal` instead of `localhost` for `INFLUX_URL` and `POSTGRES_HOST` (the compose file already maps it).
3. Run the connection check: `python -m app.storage.verify` (from `backend/`). Expect ✅ for Postgres and ✅ for InfluxDB.
4. Start the app and open http://localhost:8000/health — it should say `storage_mode: db`, `influx: ok`, `postgres: ok`.
5. Let the simulator run for a minute, then in the Influx UI (**Data Explorer → telemetry_raw → telemetry**) you will see live points, and in Postgres `SELECT count(*) FROM alerts;` rises after you inject a fault from the dashboard.

## Part 5 — Daily use
| Task | Command |
|---|---|
| Stop DBs | `docker stop oee-postgres oee-influx` |
| Start DBs | `docker start oee-postgres oee-influx` |
| See logs | `docker logs oee-postgres` / `docker logs oee-influx` |
| Backup Postgres | `docker exec oee-postgres pg_dump -U oee_user oee_db > backup.sql` |
| Wipe everything (careful!) | `docker rm -f oee-postgres oee-influx` then `docker volume rm oee_pgdata oee_influxdata` |

## Troubleshooting
- **Port already in use (5432 / 8086):** another Postgres/Influx is running. Stop it, or map a different host port (`-p 5433:5432`) and update `.env`.
- **`password authentication failed`:** `.env` password ≠ the one used in `docker run`. The password is only applied on the *first* creation of the volume — wipe the volume (Part 5) to change it.
- **App says `influx: unreachable`:** check the container is running, URL/port correct, and that you used `host.docker.internal` if the backend is in Docker.
- **`unauthorized` from Influx:** wrong token or org name — they must match the `docker run` values exactly.
- **Dashboard works but nothing persists:** `STORAGE_MODE` is still `memory`; restart the backend after editing `.env`.
- **Safe fallback:** set `STORAGE_MODE=memory` any time — the dashboard keeps working live, just without history across restarts.

## For your report/viva
Say: *"Time-series telemetry is written to InfluxDB v2 (30-day raw bucket, 1-year hourly-aggregated bucket via a Flux task); relational metadata — machines, thresholds, alerts, maintenance logs and operator feedback — lives in PostgreSQL 14."*
