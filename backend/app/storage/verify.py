"""Check your manual database setup:   python -m app.storage.verify   (run from backend/)

Writes a test row to PostgreSQL and a test point to InfluxDB, reads each back, and tells you
exactly what is missing if something is not ready.
"""
from __future__ import annotations

import sys
import time

from ..config import get_settings


def say(ok: bool | None, msg: str) -> None:
    mark = {True: "[OK]  ", False: "[FAIL]", None: "[INFO]"}[ok]
    print(f"{mark} {msg}")


def check_postgres(s) -> bool:
    from sqlalchemy import create_engine, text

    print(f"\nPostgreSQL  ->  {s.postgres_user}@{s.postgres_host}:{s.postgres_port}/{s.postgres_db}")
    try:
        eng = create_engine(s.postgres_url, connect_args={"connect_timeout": s.postgres_connect_timeout_s})
        with eng.begin() as c:
            c.execute(text("SELECT 1"))
            say(True, "connected")
            tables = {r[0] for r in c.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))}
            need = {"machines", "users", "alerts", "feedback", "maintenance_logs", "ml_models"}
            missing = sorted(need - tables)
            if missing:
                say(False, f"missing tables: {', '.join(missing)}. Run db/postgres_schema.sql "
                           "(docker cp db/postgres_schema.sql oee-postgres:/schema.sql, then psql -f /schema.sql)")
                return False
            say(True, "all 6 tables exist")
            n = c.execute(text("SELECT count(*) FROM machines")).scalar()
            say(n >= 5, f"machines table has {n} row(s)" + ("" if n >= 5 else " - the seed INSERT did not run"))
            # write + read back + clean up
            c.execute(text("""INSERT INTO maintenance_logs (id, machine_id, action, payload)
                              SELECT -1, id, 'verify', '{}'::jsonb FROM machines LIMIT 1
                              ON CONFLICT (id) DO UPDATE SET action = 'verify'"""))
            got = c.execute(text("SELECT action FROM maintenance_logs WHERE id = -1")).scalar()
            c.execute(text("DELETE FROM maintenance_logs WHERE id = -1"))
            say(got == "verify", "wrote, read back and removed a test row")
            return got == "verify"
    except Exception as exc:
        say(False, str(exc).strip().splitlines()[0])
        print("       hints: is the container running (docker ps)? POSTGRES_HOST/PORT/USER/PASSWORD in .env must match your "
              "`docker run` command; the password is only applied the first time the volume is created.")
        return False


def check_influx(s) -> bool:
    print(f"\nInfluxDB    ->  {s.influx_url}  org={s.influx_org}")
    try:
        from influxdb_client import InfluxDBClient, Point
        from influxdb_client.client.write_api import SYNCHRONOUS

        with InfluxDBClient(url=s.influx_url, token=s.influx_token, org=s.influx_org, timeout=6000) as cli:
            if not cli.ping():
                say(False, "server did not answer /ping - is the container running and INFLUX_URL right?")
                return False
            say(True, "server reachable")
            buckets = cli.buckets_api()
            ok = True
            for name in (s.influx_bucket_raw, s.influx_bucket_agg):
                b = buckets.find_bucket_by_name(name)
                if b is None:
                    say(False, f"bucket '{name}' not found - create it (see DATABASE_MANUAL_SETUP_GUIDE.md, Part 3)")
                    ok = False
                else:
                    days = (b.retention_rules[0].every_seconds // 86400) if b.retention_rules else 0
                    say(True, f"bucket '{name}' exists (retention {days or 'infinite'} days)")
            if not ok:
                return False
            tag = f"VERIFY_{int(time.time())}"
            w = cli.write_api(write_options=SYNCHRONOUS)
            w.write(bucket=s.influx_bucket_raw, org=s.influx_org,
                    record=Point("telemetry").tag("machine_id", tag).field("temperature", 71.2).field("vibration", 2.1))
            rows = cli.query_api().query(f'from(bucket:"{s.influx_bucket_raw}") |> range(start: -5m) '
                                         f'|> filter(fn:(r)=> r.machine_id == "{tag}")')
            n = sum(len(t.records) for t in rows)
            say(n >= 2, f"wrote a test point and read back {n} field value(s)")
            return n >= 2
    except Exception as exc:
        say(False, str(exc).strip().splitlines()[0])
        print("       hints: 'unauthorized' = wrong INFLUX_TOKEN/INFLUX_ORG (must match the docker run values exactly).")
        return False


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    s = get_settings()
    print(f"STORAGE_MODE currently = {s.storage_mode}  (set STORAGE_MODE=db in .env to use these databases)")
    pg, inf = check_postgres(s), check_influx(s)
    print()
    if pg and inf:
        say(True, "Both databases are ready. Set STORAGE_MODE=db and restart the backend.")
        return 0
    say(False, "Setup incomplete - see the messages above. The app still runs in STORAGE_MODE=memory.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
