"""slowapi limiter keyed by client IP.

Uvicorn runs with --proxy-headers, so behind Render's proxy request.client.host is the
real visitor address taken from X-Forwarded-For.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

_s = get_settings()

limiter = Limiter(key_func=get_remote_address, enabled=_s.rate_limit_enabled)

PUBLIC = _s.rate_limit_public
INGEST = _s.rate_limit_ingest
LOGIN = _s.rate_limit_login
