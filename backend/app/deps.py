"""FastAPI dependencies: database session, device API key, JWT user, admin role."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import TokenError, decode_token, hash_api_key
from app.db.session import get_db
from app.domain import Role
from app.models import ApiKey, AuditLog, User

DB = Annotated[Session, Depends(get_db)]
_bearer = HTTPBearer(auto_error=False)


def require_api_key(
    db: DB, x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None
) -> ApiKey:
    if not x_api_key or len(x_api_key) > 200:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid API key")
    key = db.scalar(
        select(ApiKey).where(ApiKey.key_hash == hash_api_key(x_api_key), ApiKey.active.is_(True))
    )
    if key is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid API key")
    now = datetime.now(UTC)
    # Avoid a write on every request: refresh "last used" at most once a minute.
    if key.last_used_at is None or now - key.last_used_at > timedelta(minutes=1):
        key.last_used_at = now
        db.commit()
    return key


def current_user(
    db: DB, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> User:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None or creds.scheme.lower() != "bearer":
        raise unauthorized
    s = get_settings()
    try:
        payload = decode_token(
            creds.credentials, "access", s.jwt_secret.get_secret_value(), s.jwt_algorithm
        )
        user_id = int(payload["sub"])
    except (TokenError, ValueError) as exc:
        raise unauthorized from exc
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != Role.ADMIN.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def audit(
    db: Session,
    action: str,
    details: dict[str, object] | None = None,
    user: User | None = None,
    request: Request | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            action=action,
            details=details or {},
            ip=client_ip(request) if request else None,
        )
    )
