"""Store status records, raise alerts for RED readings and broadcast live events."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain import Colour
from app.events import broker
from app.models import Alert, Reading, Site
from app.schemas import IngestIn
from app.services.sources import alert_out, latest_readings, to_source_out

log = logging.getLogger(__name__)


class UnknownSiteError(Exception):
    def __init__(self, site_ids: list[str]) -> None:
        super().__init__(", ".join(site_ids))
        self.site_ids = site_ids


@dataclass
class IngestOutcome:
    received: int = 0
    stored: int = 0
    alerts: list[Alert] = field(default_factory=list)
    stored_keys: set[tuple[str, datetime]] = field(default_factory=set)

    @property
    def duplicates(self) -> int:
        return self.received - self.stored


def _row(rec: IngestIn, now: datetime) -> dict[str, object]:
    return {
        "site_id": rec.source,
        "ts": rec.ts or now,
        "ph": rec.ph,
        "tds": rec.tds,
        "turb": rec.turb,
        "temp": rec.temp,
        "wqi": rec.wqi,
        "label": rec.label.value,
        "colour": rec.colour.value,
        "confidence": rec.confidence,
        "health": rec.health.value,
        "synthetic": rec.synthetic,
        "latency_ms": rec.latency_ms,
    }


def maybe_create_alert(db: Session, reading_id: int, row: dict[str, object]) -> Alert | None:
    """Create an alert unless this site already has one within ±ALERT_DEDUP_MINUTES.

    A per-site advisory lock serialises concurrent ingests, so two simultaneous RED
    records can never both create an alert.
    """
    site_id = str(row["site_id"])
    ts = row["ts"]
    assert isinstance(ts, datetime)
    db.execute(select(func.pg_advisory_xact_lock(func.hashtext("alert:" + site_id))))
    window = timedelta(minutes=get_settings().alert_dedup_minutes)
    recent = db.scalar(
        select(Alert.id)
        .where(Alert.site_id == site_id, Alert.ts > ts - window, Alert.ts < ts + window)
        .limit(1)
    )
    if recent is not None:
        return None
    alert = Alert(
        site_id=site_id,
        reading_id=reading_id,
        ts=ts,
        label=str(row["label"]),
        confidence=row["confidence"],  # type: ignore[arg-type]
        wqi=row["wqi"],  # type: ignore[arg-type]
    )
    db.add(alert)
    db.flush()
    return alert


def ingest(db: Session, records: list[IngestIn]) -> IngestOutcome:
    out = IngestOutcome(received=len(records))
    if not records:
        return out

    site_ids = sorted({r.source for r in records})
    known = set(db.scalars(select(Site.id).where(Site.id.in_(site_ids), Site.active.is_(True))))
    unknown = [s for s in site_ids if s not in known]
    if unknown:
        raise UnknownSiteError(unknown)

    now = datetime.now(UTC)
    # Last record wins if the same (site, ts) appears twice in one batch.
    rows = list({(r.source, r.ts or now): _row(r, now) for r in records}.values())
    rows.sort(key=lambda r: r["ts"])  # type: ignore[arg-type, return-value]

    stmt = (
        pg_insert(Reading)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["site_id", "ts"])
        .returning(Reading.id, Reading.site_id, Reading.ts)
    )
    inserted = {(sid, ts): rid for rid, sid, ts in db.execute(stmt).all()}
    out.stored = len(inserted)
    out.stored_keys = set(inserted)

    for row in rows:
        key = (str(row["site_id"]), row["ts"])
        if key in inserted and row["colour"] == Colour.RED.value:
            alert = maybe_create_alert(db, inserted[key], row)  # type: ignore[index]
            if alert is not None:
                out.alerts.append(alert)

    db.commit()
    log.info(
        "ingest",
        extra={
            "received": out.received,
            "stored": out.stored,
            "alerts": len(out.alerts),
            "sites": site_ids,
        },
    )
    _broadcast(db, out)
    return out


def _broadcast(db: Session, out: IngestOutcome) -> None:
    if not out.stored:
        return
    touched = sorted({sid for sid, _ in out.stored_keys})
    latest = latest_readings(db, touched)
    sites = {s.id: s for s in db.scalars(select(Site).where(Site.id.in_(touched)))}
    for sid in touched:
        reading = latest.get(sid)
        # Only announce when the newest reading changed (old backfill stays quiet).
        if reading is not None and (sid, reading.ts) in out.stored_keys:
            broker.publish("reading", to_source_out(sites[sid], reading).model_dump(mode="json"))
    for alert in out.alerts:
        broker.publish("alert", alert_out(alert, sites[alert.site_id]).model_dump(mode="json"))
