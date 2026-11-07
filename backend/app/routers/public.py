"""Public, read-only endpoints (no authentication, rate limited per IP)."""

import csv
import io
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import text

from app import __version__
from app.deps import DB
from app.models import Site
from app.ratelimit import PUBLIC, limiter
from app.schemas import AlertOut, HealthOut, SeriesOut, SourceOut, StatsOut, SummaryOut
from app.services import series as series_svc
from app.services import sources as sources_svc

router = APIRouter(prefix="/api", tags=["public"])

SitePath = Annotated[str, Path(min_length=2, max_length=64, pattern=r"^[a-z0-9_]+$")]


def _active_site_or_404(db: DB, site_id: str) -> Site:
    site = db.get(Site, site_id)
    if site is None or not site.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown site '{site_id}'")
    return site


@router.get("/health", response_model=HealthOut)
def health(db: DB) -> JSONResponse:
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - any DB failure means degraded
        db_status = "unreachable"
    body = HealthOut(
        status="ok" if db_status == "ok" else "degraded",
        database=db_status,
        version=__version__,
        time=datetime.now(UTC),
    )
    return JSONResponse(body.model_dump(mode="json"), status_code=200 if db_status == "ok" else 503)


@router.get("/sources", response_model=list[SourceOut])
@limiter.limit(PUBLIC)
def list_sources(request: Request, db: DB) -> list[SourceOut]:
    """All active sites with their latest reading. `stale` = no data for 15 minutes."""
    return sources_svc.list_sources(db)


@router.get("/sources/{site_id}", response_model=SourceOut)
@limiter.limit(PUBLIC)
def get_source(request: Request, db: DB, site_id: SitePath) -> SourceOut:
    src = sources_svc.get_source(db, site_id)
    if src is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown site '{site_id}'")
    return src


@router.get("/sources/{site_id}/readings", response_model=SeriesOut)
@limiter.limit(PUBLIC)
def get_readings(
    request: Request,
    db: DB,
    site_id: SitePath,
    hours: Annotated[int, Query(ge=1, le=24 * 365)] = 24,
) -> SeriesOut:
    """Raw data up to 24 h, 15-minute means up to 7 days, hourly means beyond."""
    _active_site_or_404(db, site_id)
    return series_svc.series(db, site_id, hours)


@router.get("/sources/{site_id}/stats", response_model=StatsOut)
@limiter.limit(PUBLIC)
def get_stats(
    request: Request,
    db: DB,
    site_id: SitePath,
    days: Annotated[int, Query(ge=1, le=90)] = 7,
) -> StatsOut:
    _active_site_or_404(db, site_id)
    return series_svc.stats(db, site_id, days)


@router.get("/alerts", response_model=list[AlertOut])
@limiter.limit(PUBLIC)
def get_alerts(
    request: Request,
    db: DB,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    site: Annotated[str | None, Query(max_length=64, pattern=r"^[a-z0-9_]*$")] = None,
    acknowledged: bool | None = None,
) -> list[AlertOut]:
    return sources_svc.list_alerts(db, limit=limit, site_id=site or None, acknowledged=acknowledged)


@router.get("/summary", response_model=SummaryOut)
@limiter.limit(PUBLIC)
def get_summary(request: Request, db: DB) -> SummaryOut:
    return sources_svc.summary(db)


@router.get(
    "/export/{site_id}.csv",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/csv": {}}}},
)
@limiter.limit(PUBLIC)
def export_csv(
    request: Request,
    db: DB,
    site_id: SitePath,
    days: Annotated[int, Query(ge=1, le=90)] = 7,
) -> StreamingResponse:
    site = _active_site_or_404(db, site_id)

    def generate() -> Iterator[str]:
        buf = io.StringIO()
        w = csv.writer(buf)
        if site.simulated:
            w.writerow([f"# {site.name_en}: SIMULATED demonstration data"])
        w.writerow(series_svc.CSV_COLUMNS)
        for row in series_svc.csv_rows(db, site_id, days):
            w.writerow(row)
            if buf.tell() > 64_000:
                yield buf.getvalue()
                buf.seek(0)
                buf.truncate()
        yield buf.getvalue()

    stamp = datetime.now(UTC).strftime("%Y%m%d")
    return StreamingResponse(
        generate(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{site_id}_{days}d_{stamp}.csv"'},
    )
