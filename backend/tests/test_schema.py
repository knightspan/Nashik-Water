"""Phase 1: migrations, seed data, constraints and bootstrap."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.bootstrap import bootstrap
from app.core.config import Settings
from app.core.security import api_key_matches, verify_password
from app.db.base import Base
from app.models import ApiKey, Reading, Site, User

EXPECTED_SITES = {
    "ugamsthan": True,
    "kushavart": True,
    "gangapur_dam": True,
    "someshwar": True,
    "ramkund": False,
    "tapovan": True,
    "nandini": True,
}


def _reading(**overrides: object) -> Reading:
    values: dict[str, object] = {
        "site_id": "ramkund",
        "ts": datetime(2026, 11, 20, 7, 35, tzinfo=UTC),
        "ph": 7.81,
        "tds": 331.2,
        "turb": 17.8,
        "temp": 24.6,
        "wqi": 241.6,
        "label": "Normal",
        "colour": "GREEN",
        "confidence": 97.0,
        "health": "ok",
        "synthetic": False,
        "latency_ms": 12.5,
    }
    values.update(overrides)
    return Reading(**values)


def test_seven_sites_seeded_with_correct_simulated_flags(db: Session) -> None:
    sites = {s.id: s for s in db.scalars(select(Site))}
    assert {k: v.simulated for k, v in sites.items()} == EXPECTED_SITES
    assert all(s.active for s in sites.values())
    assert all(s.name_mr and s.description_en and s.description_mr for s in sites.values())
    assert sites["ramkund"].lat == pytest.approx(20.0074)


def test_reading_insert_and_unique_site_ts(db: Session) -> None:
    db.add(_reading())
    db.flush()
    db.add(_reading(ph=7.0))
    with pytest.raises(IntegrityError):
        db.flush()


@pytest.mark.parametrize(
    "field,value",
    [
        ("ph", 14.5),
        ("tds", -1.0),
        ("turb", 3001.0),
        ("temp", 51.0),
        ("confidence", 101.0),
        ("label", "Bad"),
        ("colour", "BLUE"),
        ("health", "broken"),
        ("site_id", "unknown_site"),
    ],
)
def test_reading_constraints_reject_bad_values(db: Session, field: str, value: object) -> None:
    db.add(_reading(**{field: value}))
    with pytest.raises(IntegrityError):
        db.flush()


def test_offline_reading_may_have_null_values(db: Session) -> None:
    db.add(
        _reading(ph=None, tds=None, turb=None, temp=None, wqi=None, colour="GREY", health="offline")
    )
    db.flush()


def test_site_id_must_be_slug(db: Session) -> None:
    db.add(Site(id="Bad Id", name_en="x", name_mr="x", kind="river", lat=20, lon=73))
    with pytest.raises(IntegrityError):
        db.flush()


def test_bootstrap_is_idempotent(db: Session) -> None:
    settings = Settings()
    first = bootstrap(db, settings)
    second = bootstrap(db, settings)
    assert len(first) == 2
    assert second == []

    admin = db.scalar(select(User).where(User.email == "admin@test.local"))
    assert admin is not None and admin.role == "admin"
    assert verify_password("test-admin-password", admin.password_hash)
    assert not verify_password("wrong", admin.password_hash)

    keys = list(db.scalars(select(ApiKey)))
    assert len(keys) == 1
    assert api_key_matches("test-ingest-key-0123456789abcdef", keys[0].key_hash)
    assert "test-ingest" not in keys[0].key_hash  # only the digest is stored


def test_bootstrap_does_not_restore_a_rotated_key(db: Session) -> None:
    settings = Settings()
    bootstrap(db, settings)
    key = db.scalar(select(ApiKey))
    assert key is not None
    key.active = False
    db.flush()
    bootstrap(db, settings)
    assert db.scalar(select(func.count()).select_from(ApiKey)) == 1
    assert db.scalar(select(ApiKey.active)) is False


def test_models_match_migrations(engine: Engine) -> None:
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        diff = compare_metadata(ctx, Base.metadata)
    assert diff == []
