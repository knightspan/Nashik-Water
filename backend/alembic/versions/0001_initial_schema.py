"""Initial schema: sites, readings, readings_hourly, alerts, users, api_keys, audit_log.

Revision ID: 0001
Revises:
Create Date: 2026-11-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of the vocabularies at the time of this migration.
LABELS = ("Normal", "Natural change", "Contamination", "Sensor check", "Learning baseline")
COLOURS = ("GREEN", "AMBER", "RED", "GREY")
HEALTH = ("ok", "offline", "flatline", "out_of_range")
ROLES = ("admin", "viewer")

TZ = sa.DateTime(timezone=True)


def _in(column: str, values: Sequence[str]) -> str:
    quoted = ", ".join("'" + v + "'" for v in values)
    return f"{column} IN ({quoted})"


def _range(column: str, low: float, high: float) -> str:
    return f"{column} IS NULL OR ({column} >= {low} AND {column} <= {high})"


def upgrade() -> None:
    op.create_table(
        "sites",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("name_en", sa.String(200), nullable=False),
        sa.Column("name_mr", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("simulated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("description_en", sa.Text(), nullable=False, server_default=""),
        sa.Column("description_mr", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_sites"),
        sa.CheckConstraint("id ~ '^[a-z0-9_]{2,64}$'", name="ck_sites_id_slug"),
        sa.CheckConstraint("lat >= -90 AND lat <= 90", name="ck_sites_lat_range"),
        sa.CheckConstraint("lon >= -180 AND lon <= 180", name="ck_sites_lon_range"),
    )

    op.create_table(
        "readings",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("site_id", sa.String(64), nullable=False),
        sa.Column("ts", TZ, nullable=False),
        sa.Column("ph", sa.Float()),
        sa.Column("tds", sa.Float()),
        sa.Column("turb", sa.Float()),
        sa.Column("temp", sa.Float()),
        sa.Column("wqi", sa.Float()),
        sa.Column("label", sa.String(32), nullable=False),
        sa.Column("colour", sa.String(8), nullable=False),
        sa.Column("confidence", sa.Float()),
        sa.Column("health", sa.String(16), nullable=False, server_default="ok"),
        sa.Column("synthetic", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("latency_ms", sa.Float()),
        sa.Column("received_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_readings"),
        sa.ForeignKeyConstraint(
            ["site_id"], ["sites.id"], name="fk_readings_site_id_sites", ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("site_id", "ts", name="uq_readings_site_id_ts"),
        sa.CheckConstraint(_range("ph", 0, 14), name="ck_readings_ph_range"),
        sa.CheckConstraint(_range("tds", 0, 2000), name="ck_readings_tds_range"),
        sa.CheckConstraint(_range("turb", 0, 3000), name="ck_readings_turb_range"),
        sa.CheckConstraint(_range("temp", 0, 50), name="ck_readings_temp_range"),
        sa.CheckConstraint(_range("confidence", 0, 100), name="ck_readings_confidence_range"),
        sa.CheckConstraint("wqi IS NULL OR wqi >= 0", name="ck_readings_wqi_non_negative"),
        sa.CheckConstraint(_in("label", LABELS), name="ck_readings_label_valid"),
        sa.CheckConstraint(_in("colour", COLOURS), name="ck_readings_colour_valid"),
        sa.CheckConstraint(_in("health", HEALTH), name="ck_readings_health_valid"),
    )
    op.create_index("ix_readings_ts", "readings", ["ts"])
    op.create_index("ix_readings_site_id_ts_desc", "readings", ["site_id", sa.text("ts DESC")])
    op.create_index("ix_readings_received_at", "readings", ["received_at"])

    hourly_cols = [
        sa.Column(f"{param}_{agg}", sa.Float())
        for param in ("ph", "tds", "turb", "temp", "wqi")
        for agg in ("mean", "min", "max")
    ]
    op.create_table(
        "readings_hourly",
        sa.Column("site_id", sa.String(64), nullable=False),
        sa.Column("hour", TZ, nullable=False),
        sa.Column("n", sa.Integer(), nullable=False),
        *hourly_cols,
        sa.Column("n_green", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_amber", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_red", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_grey", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("site_id", "hour", name="pk_readings_hourly"),
        sa.ForeignKeyConstraint(
            ["site_id"], ["sites.id"], name="fk_readings_hourly_site_id_sites", ondelete="RESTRICT"
        ),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("last_login_at", TZ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint(_in("role", ROLES), name="ck_users_role_valid"),
        sa.CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
    )

    op.create_table(
        "alerts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("site_id", sa.String(64), nullable=False),
        sa.Column("reading_id", sa.BigInteger()),
        sa.Column("ts", TZ, nullable=False),
        sa.Column("label", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float()),
        sa.Column("wqi", sa.Float()),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("acknowledged_by", sa.String(320)),
        sa.Column("acknowledged_at", TZ),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_alerts"),
        sa.ForeignKeyConstraint(
            ["site_id"], ["sites.id"], name="fk_alerts_site_id_sites", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reading_id"],
            ["readings.id"],
            name="fk_alerts_reading_id_readings",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(_in("label", LABELS), name="ck_alerts_label_valid"),
    )
    op.create_index("ix_alerts_site_id_ts_desc", "alerts", ["site_id", sa.text("ts DESC")])
    op.create_index("ix_alerts_ts_desc", "alerts", [sa.text("ts DESC")])

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), sa.Identity(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("prefix", sa.String(16), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.String(320)),
        sa.Column("created_at", TZ, nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", TZ),
        sa.Column("last_used_at", TZ),
        sa.PrimaryKeyConstraint("id", name="pk_api_keys"),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("user_id", sa.Integer()),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column(
            "details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("ip", sa.String(64)),
        sa.Column("ts", TZ, nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_audit_log_user_id_users", ondelete="SET NULL"
        ),
    )
    op.create_index("ix_audit_log_ts_desc", "audit_log", [sa.text("ts DESC")])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("api_keys")
    op.drop_table("alerts")
    op.drop_table("users")
    op.drop_table("readings_hourly")
    op.drop_table("readings")
    op.drop_table("sites")
