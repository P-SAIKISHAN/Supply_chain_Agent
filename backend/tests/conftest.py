from __future__ import annotations

import sys
import tempfile
from pathlib import Path
import os

import anyio
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

LOCAL_TMP_ROOT = BACKEND_ROOT / ".pytest-tmp"
LOCAL_TMP_ROOT.mkdir(exist_ok=True)
os.environ.setdefault("TMP", str(LOCAL_TMP_ROOT))
os.environ.setdefault("TEMP", str(LOCAL_TMP_ROOT))
os.environ.setdefault("TMPDIR", str(LOCAL_TMP_ROOT))
tempfile.tempdir = str(LOCAL_TMP_ROOT)

if not hasattr(anyio, "start_blocking_portal"):
    try:
        from anyio.from_thread import start_blocking_portal as _start_blocking_portal
    except ImportError:  # pragma: no cover - fallback for unusual anyio builds
        _start_blocking_portal = None
    if _start_blocking_portal is not None:
        anyio.start_blocking_portal = _start_blocking_portal  # type: ignore[attr-defined]

try:
    import python_multipart as _python_multipart

    # Starlette still imports `multipart`, but some environments also ship an
    # older/conflicting `multipart` package that triggers deprecation warnings.
    # Point that import path at python_multipart so the test stack stays quiet.
    sys.modules.setdefault("multipart", _python_multipart)
    sys.modules.setdefault("multipart.multipart", _python_multipart.multipart)
except ImportError:  # pragma: no cover - python-multipart should be installed
    pass

from fastapi.testclient import TestClient

from app.api.deps import get_db as api_get_db
from app.core import database as database_module
from app.core.database import Base, get_db
from app.core.config import settings
from app.main import app
from app.models import *  # noqa: F403
from app.scripts.seed_demo_data import (  # noqa: F401
    seed_commodity_prices,
    seed_corridors,
    seed_geopolitical_events,
    seed_ports,
    seed_refineries,
    seed_risk_scores,
    seed_sanctions_events,
    seed_scenarios,
    seed_shipments,
    seed_supplier_countries,
    seed_users,
)


def _seed_demo_database(db):
    users = seed_users(db)
    countries = seed_supplier_countries(db)
    corridors = seed_corridors(db)
    ports = seed_ports(db)
    refineries = seed_refineries(db, ports)
    seed_shipments(db, countries, corridors, ports)
    seed_geopolitical_events(db)
    seed_sanctions_events(db)
    seed_commodity_prices(db)
    seed_risk_scores(db, countries, corridors, refineries)
    seed_scenarios(db, users["admin"], refineries)
    db.commit()


@pytest.fixture()
def session_factory(tmp_path):
    db_path = tmp_path / "test_backend.db"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )
    Base.metadata.create_all(bind=engine)

    seed_db = TestingSessionLocal()
    try:
        _seed_demo_database(seed_db)
    finally:
        seed_db.close()

    yield TestingSessionLocal

    engine.dispose()


@pytest.fixture()
def client(session_factory):
    original_scheduler = settings.enable_scheduler
    settings.enable_scheduler = False
    settings.demo_mode = True

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[api_get_db] = override_get_db
    database_module.SessionLocal = session_factory

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        settings.enable_scheduler = original_scheduler


@pytest.fixture()
def auth_headers(client):
    email = "test.user@example.com"
    password = "SecurePass123!"

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test User",
            "email": email,
            "password": password,
            "role": "analyst",
        },
    )
    if register_response.status_code != 201:
        raise AssertionError(register_response.text)

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    if login_response.status_code != 200:
        raise AssertionError(login_response.text)

    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
