"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import ClassVar

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app import __version__
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.events import broker
from app.ratelimit import limiter
from app.retention import run_retention
from app.routers import admin, auth, ingest, public, stream

settings = get_settings()
configure_logging(settings.log_level)
log = logging.getLogger("app")


async def _retention_loop() -> None:
    interval = settings.retention_interval_minutes * 60
    await asyncio.sleep(30)  # let start-up finish first
    while True:
        try:
            await asyncio.to_thread(_retention_once)
        except Exception:
            log.exception("retention job failed")
        await asyncio.sleep(interval)


def _retention_once() -> None:
    with SessionLocal() as db:
        run_retention(db)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    broker.bind(asyncio.get_running_loop())
    task = asyncio.create_task(_retention_loop()) if settings.retention_task_enabled else None
    log.info("startup", extra={"version": __version__, "environment": settings.environment})
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


class RequestLogMiddleware:
    """Pure ASGI (safe for SSE streams): JSON access log + basic security headers."""

    SECURITY_HEADERS: ClassVar[list[tuple[bytes, bytes]]] = [
        (b"x-content-type-options", b"nosniff"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (b"x-frame-options", b"DENY"),
    ]

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.extend(self.SECURITY_HEADERS)
                if settings.environment == "production":
                    headers.append(
                        (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                    )
                message["headers"] = headers
                if scope["path"] == "/api/stream":
                    log.info("sse connect", extra={"status": status_code})
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            if scope["path"] != "/api/stream":
                log.info(
                    "request",
                    extra={
                        "method": scope["method"],
                        "path": scope["path"],
                        "status": status_code,
                        "ms": round((time.perf_counter() - start) * 1000, 1),
                    },
                )


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "Smart Water Quality Monitoring and Anomaly Detection System for multiple water "
        "sources in Nashik.\n\n"
        "* **Public** endpoints need no authentication (60 requests/minute per IP).\n"
        "* **Device** endpoints need the `X-API-Key` header (600 requests/minute).\n"
        "* **Admin** endpoints need `Authorization: Bearer <access token>` from "
        "`/api/auth/login`."
    ),
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    expose_headers=["Content-Disposition"],
    max_age=600,
)
app.add_middleware(RequestLogMiddleware)

app.include_router(public.router)
app.include_router(stream.router)
app.include_router(ingest.router)
app.include_router(auth.router)
app.include_router(admin.router)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/health"}
