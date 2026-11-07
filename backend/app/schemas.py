"""Pydantic request/response models. Field names of IngestIn are the Pi's data contract."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain import Colour, Health, Label, Role
from app.wqi import wqi_band

SiteId = Annotated[str, Field(min_length=2, max_length=64, pattern=r"^[a-z0-9_]+$")]

# --------------------------------------------------------------------------- ingest


class IngestIn(BaseModel):
    """One status record per site, as POSTed by the Raspberry Pi (or the simulator)."""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "source": "ramkund",
                "colour": "GREEN",
                "label": "Normal",
                "confidence": 97.0,
                "wqi": 241.6,
                "ph": 7.81,
                "tds": 331.2,
                "turb": 17.8,
                "temp": 24.6,
                "health": "ok",
                "synthetic": False,
                "latency_ms": 12.5,
                "updated": "2026-11-20 13:05:00",
                "ts": "2026-11-20T07:35:00Z",
            }
        },
    )

    source: SiteId
    colour: Colour
    label: Label
    confidence: float | None = Field(default=None, ge=0, le=100)
    wqi: float | None = Field(default=None, ge=0, le=1_000_000)
    ph: float | None = Field(default=None, ge=0, le=14)
    tds: float | None = Field(default=None, ge=0, le=2000)
    turb: float | None = Field(default=None, ge=0, le=3000)
    temp: float | None = Field(default=None, ge=0, le=50)
    health: Health = Health.OK
    synthetic: bool = False
    latency_ms: float | None = Field(default=None, ge=0, le=600_000)
    updated: str | None = Field(default=None, max_length=40, description="Pi local time (info)")
    ts: datetime | None = Field(default=None, description="ISO 8601; server UTC time if omitted")

    @field_validator("ts")
    @classmethod
    def _ts_aware_and_not_future(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        if v.tzinfo is None:
            v = v.replace(tzinfo=UTC)
        if v > datetime.now(UTC) + timedelta(minutes=10):
            raise ValueError("ts is in the future")
        return v


class IngestResult(BaseModel):
    stored: bool
    duplicate: bool
    alert_id: int | None = None


class BatchResult(BaseModel):
    received: int
    stored: int
    duplicates: int
    alerts_created: int


# --------------------------------------------------------------------------- public


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ts: datetime
    ph: float | None
    tds: float | None
    turb: float | None
    temp: float | None
    wqi: float | None
    label: str
    colour: str
    confidence: float | None
    health: str
    synthetic: bool
    latency_ms: float | None = None
    wqi_band: str | None = None

    @classmethod
    def build(cls, obj: object) -> ReadingOut:
        r = cls.model_validate(obj, from_attributes=True)
        r.wqi_band = wqi_band(r.wqi)
        return r


class SiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name_en: str
    name_mr: str
    kind: str
    lat: float
    lon: float
    simulated: bool
    active: bool
    description_en: str
    description_mr: str


class SourceOut(SiteOut):
    latest: ReadingOut | None
    stale: bool
    status_colour: Colour = Field(description="Colour to display: GREY when stale or no data")


class SeriesPoint(BaseModel):
    ts: datetime
    ph: float | None
    tds: float | None
    turb: float | None
    temp: float | None
    wqi: float | None
    colour: str | None
    n: int = 1


class SeriesOut(BaseModel):
    site_id: str
    hours: int
    resolution: Literal["raw", "15min", "1h"]
    points: list[SeriesPoint]


class ParamStats(BaseModel):
    min: float | None
    max: float | None
    mean: float | None
    median: float | None


class StatsOut(BaseModel):
    site_id: str
    days: int
    count: int
    params: dict[str, ParamStats]
    wqi_bands: dict[str, float] = Field(description="Percent of readings in each WQI band")
    colours: dict[str, float] = Field(description="Percent of readings in each colour")


class AlertOut(BaseModel):
    id: int
    site_id: str
    site_name_en: str
    site_name_mr: str
    ts: datetime
    label: str
    confidence: float | None
    wqi: float | None
    acknowledged: bool
    acknowledged_by: str | None
    acknowledged_at: datetime | None
    note: str | None


class SummaryOut(BaseModel):
    colours: dict[str, int]
    sites: int
    stale_sites: int
    active_alerts: int
    last_update: datetime | None


class HealthOut(BaseModel):
    status: str
    database: str
    version: str
    time: datetime


# --------------------------------------------------------------------------- auth


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=72)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v:
            raise ValueError("invalid email")
        return v


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=2000)


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: Role
    created_at: datetime
    last_login_at: datetime | None


# --------------------------------------------------------------------------- admin


class SiteCreate(BaseModel):
    id: SiteId
    name_en: str = Field(min_length=1, max_length=200)
    name_mr: str = Field(min_length=1, max_length=200)
    kind: str = Field(min_length=1, max_length=40)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    simulated: bool = False
    active: bool = True
    description_en: str = Field(default="", max_length=2000)
    description_mr: str = Field(default="", max_length=2000)


class SiteUpdate(BaseModel):
    name_en: str | None = Field(default=None, min_length=1, max_length=200)
    name_mr: str | None = Field(default=None, min_length=1, max_length=200)
    kind: str | None = Field(default=None, min_length=1, max_length=40)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    simulated: bool | None = None
    active: bool | None = None
    description_en: str | None = Field(default=None, max_length=2000)
    description_mr: str | None = Field(default=None, max_length=2000)


class AckIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    prefix: str
    active: bool
    created_by: str | None
    created_at: datetime
    revoked_at: datetime | None
    last_used_at: datetime | None


class ApiKeyRotateIn(BaseModel):
    name: str = Field(default="rotated key", min_length=1, max_length=100)
    revoke_previous: bool = True


class ApiKeyRotateOut(BaseModel):
    key: str = Field(description="Shown once. Store it in the Pi's .env as WEB_API_KEY.")
    api_key: ApiKeyOut
    revoked: int


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    user_email: str | None = None
    action: str
    details: dict[str, object]
    ip: str | None
    ts: datetime


class SiteIngestHealth(BaseModel):
    site_id: str
    name_en: str
    simulated: bool
    last_received_at: datetime | None
    last_ts: datetime | None
    messages_last_hour: int
    hourly: list[int] = Field(description="Messages per hour, oldest first, last 24 hours")


class IngestHealthOut(BaseModel):
    generated_at: datetime
    sites: list[SiteIngestHealth]
