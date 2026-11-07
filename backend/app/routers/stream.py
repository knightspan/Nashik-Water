"""Server-Sent Events: pushes `reading` and `alert` events as data is ingested."""

from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.events import Broker, broker
from app.ratelimit import PUBLIC, limiter

router = APIRouter(prefix="/api", tags=["public"])


async def sse_events(source: Broker) -> AsyncIterator[dict[str, str | int]]:
    """`hello` first (tells the browser to retry after 5 s), then every published event."""
    async with source.subscribe() as queue:
        yield {"event": "hello", "data": "{}", "retry": 5000}
        while True:
            event, payload = await queue.get()
            yield {"event": event, "data": payload}


@router.get("/stream")
@limiter.limit(PUBLIC)
async def stream(request: Request) -> EventSourceResponse:
    """Event types: `hello` on connect, `reading` (a SourceOut), `alert` (an AlertOut).
    A comment ping is sent every 15 s to keep proxies from closing the connection."""

    return EventSourceResponse(
        sse_events(broker),
        ping=15,
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
