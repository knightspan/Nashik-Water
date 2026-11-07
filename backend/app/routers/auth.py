"""Admin login with JWT (access 30 min, refresh 7 days) in the Authorization header."""

import secrets
from datetime import UTC, datetime, timedelta
from functools import cache

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import TokenError, create_token, decode_token, hash_password, verify_password
from app.deps import DB, CurrentUser, audit
from app.models import User
from app.ratelimit import LOGIN, limiter
from app.schemas import LoginIn, RefreshIn, TokenOut, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@cache
def _dummy_hash() -> str:
    """Hash of a random password, so a login for an unknown email costs as much as a real one."""
    return hash_password(secrets.token_urlsafe(16))


def _tokens(user: User) -> TokenOut:
    s = get_settings()
    secret = s.jwt_secret.get_secret_value()
    return TokenOut(
        access_token=create_token(
            user.id,
            user.role,
            "access",
            secret,
            s.jwt_algorithm,
            timedelta(minutes=s.access_token_minutes),
        ),
        refresh_token=create_token(
            user.id,
            user.role,
            "refresh",
            secret,
            s.jwt_algorithm,
            timedelta(days=s.refresh_token_days),
        ),
        expires_in=s.access_token_minutes * 60,
    )


@router.post("/login", response_model=TokenOut)
@limiter.limit(LOGIN)
def login(request: Request, db: DB, body: LoginIn) -> TokenOut:
    user = db.scalar(select(User).where(User.email == body.email))
    ok = verify_password(body.password, user.password_hash if user else _dummy_hash())
    if user is None or not ok or not user.is_active:
        audit(db, "auth.login_failed", {"email": body.email}, request=request)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    user.last_login_at = datetime.now(UTC)
    audit(db, "auth.login", {}, user=user, request=request)
    db.commit()
    return _tokens(user)


@router.post("/refresh", response_model=TokenOut)
@limiter.limit(LOGIN)
def refresh(request: Request, db: DB, body: RefreshIn) -> TokenOut:
    s = get_settings()
    try:
        payload = decode_token(
            body.refresh_token, "refresh", s.jwt_secret.get_secret_value(), s.jwt_algorithm
        )
        user = db.get(User, int(payload["sub"]))
    except (TokenError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token") from exc
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    return _tokens(user)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user
