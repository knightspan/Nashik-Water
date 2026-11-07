"""Hourly roll-up into readings_hourly (kept forever) and pruning of old raw readings.

Runs every RETENTION_INTERVAL_MINUTES inside the API process, and on demand with
``python -m app.cli retention``. A Postgres advisory lock stops two runs overlapping.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Reading, ReadingHourly

log = logging.getLogger(__name__)

LOCK_KEY = 815_001  # arbitrary, unique to this job
PARAMS = ("ph", "tds", "turb", "temp", "wqi")


@dataclass
class RetentionResult:
    hours_upserted: int
    readings_deleted: int
    skipped: bool = False


def rollup(db: Session, since: datetime | None, until: datetime) -> int:
    """Upsert hourly aggregates for complete hours in [since, until)."""
    hour = func.date_trunc("hour", Reading.ts, "UTC")
    aggs = [hour.label("hour"), Reading.site_id, func.count().label("n")]
    for p in PARAMS:
        c = getattr(Reading, p)
        aggs += [func.avg(c), func.min(c), func.max(c)]
    for colour in ("GREEN", "AMBER", "RED", "GREY"):
        aggs.append(func.count().filter(Reading.colour == colour))
    src = select(*aggs).where(Reading.ts < until)
    if since is not None:
        src = src.where(Reading.ts >= since)
    src = src.group_by(hour, Reading.site_id)

    target_cols = ["hour", "site_id", "n"]
    for p in PARAMS:
        target_cols += [f"{p}_mean", f"{p}_min", f"{p}_max"]
    target_cols += ["n_green", "n_amber", "n_red", "n_grey"]

    ins = pg_insert(ReadingHourly).from_select(target_cols, src)
    update_cols = {c: ins.excluded[c] for c in target_cols if c not in ("hour", "site_id")}
    update_cols["updated_at"] = func.now()
    stmt = ins.on_conflict_do_update(index_elements=["site_id", "hour"], set_=update_cols)
    result = db.execute(stmt)
    return int(result.rowcount or 0)


def run_retention(db: Session, full: bool = False, now: datetime | None = None) -> RetentionResult:
    settings = get_settings()
    now = now or datetime.now(UTC)
    if not db.scalar(select(func.pg_try_advisory_xact_lock(LOCK_KEY))):
        db.rollback()
        return RetentionResult(0, 0, skipped=True)

    current_hour = now.replace(minute=0, second=0, microsecond=0)
    cutoff = now - timedelta(days=settings.retention_days)

    # Recent complete hours (late data from the Pi's offline queue is picked up for 3 days)...
    upserted = rollup(db, None if full else current_hour - timedelta(days=3), current_hour)
    # ...and every hour that is about to be pruned, so nothing is lost.
    cutoff_hour = cutoff.replace(minute=0, second=0, microsecond=0)
    if not full:
        upserted += rollup(db, None, cutoff_hour + timedelta(hours=1))
    deleted = db.execute(delete(Reading).where(Reading.ts < cutoff_hour)).rowcount or 0
    db.commit()
    log.info("retention", extra={"hours_upserted": upserted, "readings_deleted": deleted})
    return RetentionResult(upserted, int(deleted))
