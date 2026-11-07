"""Latest status per site, the summary bar and alert listing."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain import Colour
from app.models import Alert, Reading, Site
from app.schemas import AlertOut, ReadingOut, SiteOut, SourceOut, SummaryOut


def latest_readings(db: Session, site_ids: Iterable[str] | None = None) -> dict[str, Reading]:
    """Newest reading per site (Postgres DISTINCT ON, served by ix_readings_site_id_ts_desc)."""
    stmt = select(Reading).distinct(Reading.site_id).order_by(Reading.site_id, Reading.ts.desc())
    if site_ids is not None:
        stmt = stmt.where(Reading.site_id.in_(list(site_ids)))
    return {r.site_id: r for r in db.scalars(stmt)}


def is_stale(reading: Reading | None, now: datetime | None = None) -> bool:
    if reading is None:
        return True
    now = now or datetime.now(UTC)
    return now - reading.ts > timedelta(minutes=get_settings().stale_after_minutes)


def to_source_out(site: Site, reading: Reading | None, now: datetime | None = None) -> SourceOut:
    stale = is_stale(reading, now)
    colour = Colour.GREY if stale or reading is None else Colour(reading.colour)
    return SourceOut(
        **SiteOut.model_validate(site).model_dump(),
        latest=ReadingOut.build(reading) if reading else None,
        stale=stale,
        status_colour=colour,
    )


def list_sources(db: Session, include_inactive: bool = False) -> list[SourceOut]:
    stmt = select(Site).order_by(Site.lon)
    if not include_inactive:
        stmt = stmt.where(Site.active.is_(True))
    sites = list(db.scalars(stmt))
    latest = latest_readings(db, [s.id for s in sites])
    now = datetime.now(UTC)
    return [to_source_out(s, latest.get(s.id), now) for s in sites]


def get_source(db: Session, site_id: str) -> SourceOut | None:
    site = db.get(Site, site_id)
    if site is None or not site.active:
        return None
    return to_source_out(site, latest_readings(db, [site_id]).get(site_id))


def summary(db: Session) -> SummaryOut:
    sources = list_sources(db)
    colours = {c.value: 0 for c in Colour}
    for s in sources:
        colours[s.status_colour.value] += 1
    active_alerts = db.scalar(
        select(func.count()).select_from(Alert).where(Alert.acknowledged.is_(False))
    )
    last = max((s.latest.ts for s in sources if s.latest), default=None)
    return SummaryOut(
        colours=colours,
        sites=len(sources),
        stale_sites=sum(1 for s in sources if s.stale),
        active_alerts=int(active_alerts or 0),
        last_update=last,
    )


def alert_out(alert: Alert, site: Site) -> AlertOut:
    return AlertOut(
        id=alert.id,
        site_id=alert.site_id,
        site_name_en=site.name_en,
        site_name_mr=site.name_mr,
        ts=alert.ts,
        label=alert.label,
        confidence=alert.confidence,
        wqi=alert.wqi,
        acknowledged=alert.acknowledged,
        acknowledged_by=alert.acknowledged_by,
        acknowledged_at=alert.acknowledged_at,
        note=alert.note,
    )


def list_alerts(
    db: Session, limit: int = 50, site_id: str | None = None, acknowledged: bool | None = None
) -> list[AlertOut]:
    stmt = select(Alert, Site).join(Site, Site.id == Alert.site_id).order_by(Alert.ts.desc())
    if site_id:
        stmt = stmt.where(Alert.site_id == site_id)
    if acknowledged is not None:
        stmt = stmt.where(Alert.acknowledged.is_(acknowledged))
    return [alert_out(a, s) for a, s in db.execute(stmt.limit(limit)).all()]
