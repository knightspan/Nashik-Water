"""First-run setup: create the admin user and the first ingest API key from env vars.

Safe to run on every start:
- the admin is created only if no user with ADMIN_EMAIL exists (an existing password
  is never overwritten);
- INGEST_API_KEY is stored only when the api_keys table is empty, so a key that an
  admin has rotated away is never brought back by a redeploy.
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import api_key_display_prefix, hash_api_key, hash_password
from app.domain import Role
from app.models import ApiKey, AuditLog, User

log = logging.getLogger(__name__)


def bootstrap(db: Session, settings: Settings) -> list[str]:
    done: list[str] = []

    if settings.admin_email and settings.admin_password:
        email = settings.admin_email.strip().lower()
        if db.scalar(select(User).where(User.email == email)) is None:
            db.add(
                User(
                    email=email,
                    password_hash=hash_password(settings.admin_password.get_secret_value()),
                    role=Role.ADMIN.value,
                )
            )
            db.add(AuditLog(action="bootstrap.admin_created", details={"email": email}))
            done.append(f"admin user {email} created")

    if settings.ingest_api_key:
        key = settings.ingest_api_key.get_secret_value()
        if db.scalar(select(func.count()).select_from(ApiKey)) == 0:
            db.add(
                ApiKey(
                    name="bootstrap (INGEST_API_KEY)",
                    prefix=api_key_display_prefix(key),
                    key_hash=hash_api_key(key),
                    created_by="bootstrap",
                )
            )
            db.add(AuditLog(action="bootstrap.api_key_created", details={}))
            done.append("ingest API key stored")

    db.commit()
    for msg in done:
        log.info("bootstrap", extra={"event": msg})
    return done
