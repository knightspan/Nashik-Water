"""Device endpoints, authenticated with the X-API-Key header."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status

from app.core.config import get_settings
from app.deps import DB, require_api_key
from app.models import ApiKey
from app.ratelimit import INGEST, limiter
from app.schemas import BatchResult, IngestIn, IngestResult
from app.services.ingest import UnknownSiteError, ingest

router = APIRouter(prefix="/api/ingest", tags=["device"])

ApiKeyDep = Annotated[ApiKey, Depends(require_api_key)]


def _run(db: DB, records: list[IngestIn]):  # type: ignore[no-untyped-def]
    try:
        return ingest(db, records)
    except UnknownSiteError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Unknown or inactive site id(s): {', '.join(exc.site_ids)}"
        ) from exc


@router.post("", response_model=IngestResult, status_code=status.HTTP_201_CREATED)
@limiter.limit(INGEST)
def ingest_one(request: Request, db: DB, _key: ApiKeyDep, record: IngestIn) -> IngestResult:
    """Store one status record from the Raspberry Pi. A RED record raises an alert
    (at most one per site per 30 minutes). Re-sending the same (source, ts) is a no-op."""
    out = _run(db, [record])
    return IngestResult(
        stored=out.stored == 1,
        duplicate=out.stored == 0,
        alert_id=out.alerts[0].id if out.alerts else None,
    )


@router.post("/batch", response_model=BatchResult, status_code=status.HTTP_201_CREATED)
@limiter.limit(INGEST)
def ingest_batch(
    request: Request,
    db: DB,
    _key: ApiKeyDep,
    records: Annotated[list[IngestIn], Body(min_length=1)],
) -> BatchResult:
    """Store many records at once (the Pi's offline queue, or the simulator).
    Idempotent on (source, ts): duplicates are counted, not stored twice."""
    limit = get_settings().ingest_batch_max
    if len(records) > limit:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"Batch too large (max {limit} records)"
        )
    out = _run(db, records)
    return BatchResult(
        received=out.received,
        stored=out.stored,
        duplicates=out.duplicates,
        alerts_created=len(out.alerts),
    )
