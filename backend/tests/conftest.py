"""Test fixtures.

Tests run against a real PostgreSQL database (the schema uses Postgres features such as
JSONB, regex checks and ON CONFLICT). Point TEST_DATABASE_URL at a throw-away database;
its contents are wiped at the start of the run. From the project root, `npm test` starts
the portable dev database and runs these tests against its `water_test` database.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://water:water@localhost:5433/water_test"
)
# Must be set before any app module reads settings.
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENVIRONMENT"] = "test"
os.environ.setdefault("JWT_SECRET", "test-secret-" + "x" * 40)
os.environ.setdefault("INGEST_API_KEY", "test-ingest-key-0123456789abcdef")
os.environ.setdefault("ADMIN_EMAIL", "admin@test.local")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["RETENTION_TASK_ENABLED"] = "false"

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import Engine, make_url  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _ensure_database(url: str) -> None:
    """Create the test database if it does not exist yet."""
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": target.database}
        )
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    admin.dispose()


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL.replace("%", "%%"))
    return cfg


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    _ensure_database(TEST_DB_URL)
    eng = create_engine(TEST_DB_URL)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    cfg = alembic_config()
    # Exercise the downgrade path too, then leave the schema at head.
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """A session whose work is rolled back after each test (commits become savepoints)."""
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


INGEST_KEY = "test-ingest-key-0123456789abcdef"


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    """API client whose requests share the rolled-back test session."""
    from app.bootstrap import bootstrap
    from app.core.config import Settings
    from app.db.session import get_db
    from app.main import app

    bootstrap(db, Settings())
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def key_headers() -> dict[str, str]:
    return {"X-API-Key": INGEST_KEY}


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    res = client.post(
        "/api/auth/login", json={"email": "admin@test.local", "password": "test-admin-password"}
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}
