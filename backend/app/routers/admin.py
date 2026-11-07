"""Admin endpoints (JWT with role=admin). Every change is written to the audit log."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import func, select, update

from app.core.security import api_key_display_prefix, generate_api_key, hash_api_key
from app.deps import DB, AdminUser, audit
from app.models import Alert, ApiKey, AuditLog, Reading, Site, User
from app.schemas import (
    AckIn,
    AlertOut,
    ApiKeyOut,
    ApiKeyRotateIn,
    ApiKeyRotateOut,
    AuditOut,
    IngestHealthOut,
    SiteCreate,
    SiteIngestHealth,
    SiteOut,
    SiteUpdate,
)
from app.services.sources import alert_out

router = APIRouter(prefix="/api/admin", tags=["admin"])


# --------------------------------------------------------------------------- sites


@router.get("/sites", response_model=list[SiteOut])
def list_sites(db: DB, _: AdminUser) -> list[Site]:
    """All sites, including deactivated ones."""
    return list(db.scalars(select(Site).order_by(Site.active.desc(), Site.lon)))


@router.post("/sites", response_model=SiteOut, status_code=status.HTTP_201_CREATED)
def create_site(request: Request, db: DB, user: AdminUser, body: SiteCreate) -> Site:
    if db.get(Site, body.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Site '{body.id}' already exists")
    site = Site(**body.model_dump())
    db.add(site)
    audit(db, "site.create", body.model_dump(), user=user, request=request)
    db.commit()
    return site


@router.put("/sites/{site_id}", response_model=SiteOut)
def update_site(request: Request, db: DB, user: AdminUser, site_id: str, body: SiteUpdate) -> Site:
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown site '{site_id}'")
    changes = body.model_dump(exclude_unset=True)
    before = {k: getattr(site, k) for k in changes}
    for k, v in changes.items():
        setattr(site, k, v)
    audit(
        db,
        "site.update",
        {"site_id": site_id, "before": before, "after": changes},
        user=user,
        request=request,
    )
    db.commit()
    return site


@router.delete("/sites/{site_id}", response_model=SiteOut)
def deactivate_site(request: Request, db: DB, user: AdminUser, site_id: str) -> Site:
    """Deactivate (soft-delete): the site disappears from the public map, history is kept."""
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown site '{site_id}'")
    site.active = False
    audit(db, "site.deactivate", {"site_id": site_id}, user=user, request=request)
    db.commit()
    return site


# --------------------------------------------------------------------------- alerts


@router.post("/alerts/{alert_id}/ack", response_model=AlertOut)
def acknowledge_alert(
    request: Request, db: DB, user: AdminUser, alert_id: int, body: AckIn | None = None
) -> AlertOut:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    if not alert.acknowledged:
        alert.acknowledged = True
        alert.acknowledged_by = user.email
        alert.acknowledged_at = datetime.now(UTC)
    if body and body.note is not None:
        alert.note = body.note
    audit(
        db,
        "alert.ack",
        {"alert_id": alert_id, "note": body.note if body else None},
        user=user,
        request=request,
    )
    db.commit()
    site = db.get(Site, alert.site_id)
    assert site is not None
    return alert_out(alert, site)


# --------------------------------------------------------------------------- API keys


@router.get("/apikeys", response_model=list[ApiKeyOut])
def list_api_keys(db: DB, _: AdminUser) -> list[ApiKey]:
    return list(db.scalars(select(ApiKey).order_by(ApiKey.created_at.desc())))


@router.post("/apikeys/rotate", response_model=ApiKeyRotateOut, status_code=201)
def rotate_api_key(
    request: Request, db: DB, user: AdminUser, body: ApiKeyRotateIn | None = None
) -> ApiKeyRotateOut:
    """Create a new ingest key (returned once) and, by default, revoke all others.
    Update WEB_API_KEY on the Pi (and the simulator) right after rotating."""
    body = body or ApiKeyRotateIn()
    revoked = 0
    if body.revoke_previous:
        res = db.execute(
            update(ApiKey)
            .where(ApiKey.active.is_(True))
            .values(active=False, revoked_at=datetime.now(UTC))
        )
        revoked = int(res.rowcount or 0)
    key = generate_api_key()
    row = ApiKey(
        name=body.name,
        prefix=api_key_display_prefix(key),
        key_hash=hash_api_key(key),
        created_by=user.email,
    )
    db.add(row)
    audit(
        db,
        "apikey.rotate",
        {"prefix": row.prefix, "revoked": revoked},
        user=user,
        request=request,
    )
    db.commit()
    return ApiKeyRotateOut(key=key, api_key=ApiKeyOut.model_validate(row), revoked=revoked)


# --------------------------------------------------------------------------- audit + health


@router.get("/audit", response_model=list[AuditOut])
def audit_log(
    db: DB, _: AdminUser, limit: Annotated[int, Query(ge=1, le=500)] = 100
) -> list[AuditOut]:
    rows = db.execute(
        select(AuditLog, User.email)
        .outerjoin(User, User.id == AuditLog.user_id)
        .order_by(AuditLog.ts.desc())
        .limit(limit)
    ).all()
    out = []
    for entry, email in rows:
        item = AuditOut.model_validate(entry)
        item.user_email = email
        out.append(item)
    return out


@router.get("/ingest-health", response_model=IngestHealthOut)
def ingest_health(db: DB, _: AdminUser) -> IngestHealthOut:
    """Last message per site and messages per hour (by server receive time) for 24 h."""
    now = datetime.now(UTC)
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    start = current_hour - timedelta(hours=23)
    sites = list(db.scalars(select(Site).where(Site.active.is_(True)).order_by(Site.lon)))

    last = {
        sid: (rcv, ts)
        for sid, rcv, ts in db.execute(
            select(Reading.site_id, func.max(Reading.received_at), func.max(Reading.ts)).group_by(
                Reading.site_id
            )
        )
    }
    hour = func.date_trunc("hour", Reading.received_at, "UTC")
    counts: dict[str, dict[datetime, int]] = {}
    for sid, h, n in db.execute(
        select(Reading.site_id, hour, func.count())
        .where(Reading.received_at >= start)
        .group_by(Reading.site_id, hour)
    ):
        counts.setdefault(sid, {})[h] = n
    last_hour = dict(
        db.execute(
            select(Reading.site_id, func.count())
            .where(Reading.received_at >= now - timedelta(hours=1))
            .group_by(Reading.site_id)
        ).all()
    )

    hours = [start + timedelta(hours=i) for i in range(24)]
    result = []
    for s in sites:
        per = counts.get(s.id, {})
        by_hour = {h.astimezone(UTC): n for h, n in per.items()}
        rcv, ts = last.get(s.id, (None, None))
        result.append(
            SiteIngestHealth(
                site_id=s.id,
                name_en=s.name_en,
                simulated=s.simulated,
                last_received_at=rcv,
                last_ts=ts,
                messages_last_hour=int(last_hour.get(s.id, 0)),
                hourly=[int(by_hour.get(h, 0)) for h in hours],
            )
        )
    return IngestHealthOut(generated_at=now, sites=result)
