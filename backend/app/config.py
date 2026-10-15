"""Application settings, loaded from environment variables / ``.env`` (NFR-S3: no secrets in code)."""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent

# Make the shared ``simulator`` package importable both locally (repo checkout) and in Docker
# (where it is copied next to ``app``).
for _p in (REPO_ROOT, BACKEND_DIR):
    if (_p / "simulator").is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"), str(BACKEND_DIR / ".env")), env_file_encoding="utf-8", extra="ignore"
    )

    # --- runtime modes ---------------------------------------------------------------
    ingest_mode: str = "direct"          # direct | mqtt
    storage_mode: str = "memory"         # memory | db
    machine_count: int = Field(5, ge=1, le=20)
    tick_ms: int = 500
    log_level: str = "INFO"
    log_json: bool = False
    cors_origins: str = "*"
    backfill_days: float = 7.0           # simulated history used for 1h/8h windows and reports
    sim_seed: int | None = None
    ingest_api_key: str = ""             # optional key for POST /telemetry

    # --- MQTT (SRS: MQTT over WebSockets through Mosquitto) ---------------------------
    mqtt_host: str = "localhost"
    mqtt_port: int | None = None
    mqtt_transport: str = "websockets"   # websockets | tcp
    mqtt_ws_path: str = "/"
    mqtt_username: str = ""
    mqtt_password: str = ""

    # --- thresholds / engines ---------------------------------------------------------
    anomaly_threshold: float = 85.0      # percent -> Yellow
    ml_consecutive: int = 2              # consecutive ticks above threshold before Yellow
    whatif_window_s: int = 180           # regression window (3 minutes)
    whatif_horizon_s: int = 60           # Orange when threshold crossing is within this many seconds
    whatif_min_slope: float = 0.03       # deg C per second (ignore flat/noisy trends)
    whatif_min_r2: float = 0.6
    whatif_min_points: int = 30
    model_path: str = str(BACKEND_DIR / "models" / "model.pkl")

    # --- auth (single tenant, HTTP Basic) ---------------------------------------------
    # "user:password:role,user:password:role"
    users: str = "manager:manager123:floor_manager,engineer:engineer123:maintenance_engineer,analyst:analyst123:production_analyst,admin:admin123:system_administrator"
    demo_hints: bool = True              # show demo logins on the login form
    technicians: str = "A. Kulkarni,R. Deshmukh,S. Patil,M. Shaikh"

    # --- storage: InfluxDB v2 + PostgreSQL -------------------------------------------
    influx_url: str = "http://localhost:8086"
    influx_token: str = ""
    influx_org: str = "oee-org"
    influx_bucket_raw: str = "telemetry_raw"
    influx_bucket_agg: str = "telemetry_agg"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "oee_db"
    postgres_user: str = "oee_user"
    postgres_password: str = ""

    @property
    def resolved_mqtt_port(self) -> int:
        if self.mqtt_port:
            return self.mqtt_port
        return 9001 if self.mqtt_transport == "websockets" else 1883

    @property
    def postgres_url(self) -> str:
        from urllib.parse import quote_plus

        return (f"postgresql+psycopg2://{quote_plus(self.postgres_user)}:{quote_plus(self.postgres_password)}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
