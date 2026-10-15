import os
import sys
from pathlib import Path

os.environ.setdefault("BACKFILL_DAYS", "0")
os.environ.setdefault("STORAGE_MODE", "memory")
os.environ.setdefault("INGEST_MODE", "direct")
os.environ.setdefault("LOG_LEVEL", "WARNING")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

AUTH = ("manager", "manager123")


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c
