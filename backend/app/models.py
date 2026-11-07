"""SQLAlchemy ORM models.

The Alembic migrations in ``alembic/versions`` are the source of truth for the live
schema; ``tests/test_schema.py`` checks that these models and the migrations agree.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain import Colour, Health, Label, Role


def in_list(column: str, values: Iterable[str]) -> str:
    quoted = ", ".join("'" + v + "'" for v in values)
    return f"{column} IN ({quoted})"


def in_range(column: str, low: float, high: float) -> str:
    return f"{column} IS NULL OR ({column} >= {low} AND {column} <= {high})"


TZ = DateTime(timezone=True)


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name_en: Mapped[str] = mapped_column(String(200), nullable=False)
    name_mr: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    simulated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    description_en: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    description_mr: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("id ~ '^[a-z0-9_]{2,64}$'", name="id_slug"),
        CheckConstraint("lat >= -90 AND lat <= 90", name="lat_range"),
        CheckConstraint("lon >= -180 AND lon <= 180", name="lon_range"),
    )


class Reading(Base):
    __tablename__ = "readings"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    site_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sites.id", ondelete="RESTRICT"), nullable=False
    )
    ts: Mapped[datetime] = mapped_column(TZ, nullable=False, index=True)
    ph: Mapped[float | None] = mapped_column(Float)
    tds: Mapped[float | None] = mapped_column(Float)
    turb: Mapped[float | None] = mapped_column(Float)
    temp: Mapped[float | None] = mapped_column(Float)
    wqi: Mapped[float | None] = mapped_column(Float)
    label: Mapped[str] = mapped_column(String(32), nullable=False)
    colour: Mapped[str] = mapped_column(String(8), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    health: Mapped[str] = mapped_column(String(16), nullable=False, server_default="ok")
    synthetic: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    latency_ms: Mapped[float | None] = mapped_column(Float)
    # When the server stored the row; drives the "messages per hour" ingest-health view.
    received_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("site_id", "ts", name="uq_readings_site_id_ts"),
        CheckConstraint(in_range("ph", 0, 14), name="ph_range"),
        CheckConstraint(in_range("tds", 0, 2000), name="tds_range"),
        CheckConstraint(in_range("turb", 0, 3000), name="turb_range"),
        CheckConstraint(in_range("temp", 0, 50), name="temp_range"),
        CheckConstraint(in_range("confidence", 0, 100), name="confidence_range"),
        CheckConstraint("wqi IS NULL OR wqi >= 0", name="wqi_non_negative"),
        CheckConstraint(in_list("label", [m.value for m in Label]), name="label_valid"),
        CheckConstraint(in_list("colour", [m.value for m in Colour]), name="colour_valid"),
        CheckConstraint(in_list("health", [m.value for m in Health]), name="health_valid"),
    )


Index("ix_readings_site_id_ts_desc", Reading.site_id, Reading.ts.desc())
Index("ix_readings_received_at", Reading.received_at)


class ReadingHourly(Base):
    """Hourly roll-up kept forever; raw readings are pruned after the retention period."""

    __tablename__ = "readings_hourly"

    site_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sites.id", ondelete="RESTRICT"), primary_key=True
    )
    hour: Mapped[datetime] = mapped_column(TZ, primary_key=True)
    n: Mapped[int] = mapped_column(Integer, nullable=False)
    ph_mean: Mapped[float | None] = mapped_column(Float)
    ph_min: Mapped[float | None] = mapped_column(Float)
    ph_max: Mapped[float | None] = mapped_column(Float)
    tds_mean: Mapped[float | None] = mapped_column(Float)
    tds_min: Mapped[float | None] = mapped_column(Float)
    tds_max: Mapped[float | None] = mapped_column(Float)
    turb_mean: Mapped[float | None] = mapped_column(Float)
    turb_min: Mapped[float | None] = mapped_column(Float)
    turb_max: Mapped[float | None] = mapped_column(Float)
    temp_mean: Mapped[float | None] = mapped_column(Float)
    temp_min: Mapped[float | None] = mapped_column(Float)
    temp_max: Mapped[float | None] = mapped_column(Float)
    wqi_mean: Mapped[float | None] = mapped_column(Float)
    wqi_min: Mapped[float | None] = mapped_column(Float)
    wqi_max: Mapped[float | None] = mapped_column(Float)
    n_green: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    n_amber: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    n_red: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    n_grey: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    site_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sites.id", ondelete="RESTRICT"), nullable=False
    )
    # Kept as a soft link: raw readings are pruned after 90 days, alerts are not.
    reading_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("readings.id", ondelete="SET NULL")
    )
    ts: Mapped[datetime] = mapped_column(TZ, nullable=False)
    label: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    wqi: Mapped[float | None] = mapped_column(Float)
    acknowledged: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    acknowledged_by: Mapped[str | None] = mapped_column(String(320))
    acknowledged_at: Mapped[datetime | None] = mapped_column(TZ)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(in_list("label", [m.value for m in Label]), name="label_valid"),
    )


Index("ix_alerts_site_id_ts_desc", Alert.site_id, Alert.ts.desc())
Index("ix_alerts_ts_desc", Alert.ts.desc())


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, server_default=Role.VIEWER.value)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(TZ)

    __table_args__ = (
        CheckConstraint(in_list("role", [m.value for m in Role]), name="role_valid"),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )


class ApiKey(Base):
    """Device ingest keys. Only a SHA-256 digest is stored, never the key itself."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_by: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(TZ)
    last_used_at: Mapped[datetime | None] = mapped_column(TZ)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    ip: Mapped[str | None] = mapped_column(String(64))
    ts: Mapped[datetime] = mapped_column(TZ, nullable=False, server_default=func.now())


Index("ix_audit_log_ts_desc", AuditLog.ts.desc())
