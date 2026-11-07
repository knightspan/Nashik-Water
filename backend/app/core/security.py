"""Password and API-key hashing.

Passwords use bcrypt. API keys are long random tokens, so a fast SHA-256 digest is
safe for them (no brute-force risk) and cheap enough for 600 ingest requests a minute.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt

API_KEY_PREFIX = "nwq_"
BCRYPT_MAX_BYTES = 72


class PasswordTooLongError(ValueError):
    pass


def hash_password(password: str) -> str:
    raw = password.encode("utf-8")
    if len(raw) > BCRYPT_MAX_BYTES:
        raise PasswordTooLongError("Password must be at most 72 bytes")
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    raw = password.encode("utf-8")
    if len(raw) > BCRYPT_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(raw, password_hash.encode("ascii"))
    except ValueError:
        return False


def generate_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def api_key_matches(key: str, key_hash: str) -> bool:
    return hmac.compare_digest(hash_api_key(key), key_hash)


def api_key_display_prefix(key: str) -> str:
    """First characters shown in the admin panel so keys can be told apart."""
    return key[:10]


# --------------------------------------------------------------------------- JWT

TokenType = Literal["access", "refresh"]


class TokenError(Exception):
    pass


def create_token(
    user_id: int, role: str, token_type: TokenType, secret: str, algorithm: str, ttl: timedelta
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "typ": token_type,
        "iat": now,
        "exp": now + ttl,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(token: str, expected: TokenType, secret: str, algorithm: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token, secret, algorithms=[algorithm], options={"require": ["exp", "sub", "typ"]}
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    if payload.get("typ") != expected:
        raise TokenError("wrong token type")
    return payload
