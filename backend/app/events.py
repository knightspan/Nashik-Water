"""In-process broadcaster for Server-Sent Events.

Ingest handlers run in FastAPI's thread pool, so ``publish`` hands events to the event
loop with ``call_soon_threadsafe``. Each SSE client owns a bounded queue; a client that
falls behind loses its oldest events rather than slowing everyone down.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

log = logging.getLogger(__name__)

Event = tuple[str, str]


class Broker:
    def __init__(self, queue_size: int = 200) -> None:
        self._subscribers: set[asyncio.Queue[Event]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue_size = queue_size

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @contextlib.asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[Event]]:
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=self._queue_size)
        self._subscribers.add(q)
        try:
            yield q
        finally:
            self._subscribers.discard(q)

    def publish(self, event: str, data: Any) -> None:
        """Thread-safe. Silently does nothing before the app has started."""
        if self._loop is None or self._loop.is_closed():
            return
        payload = json.dumps(data, default=str, ensure_ascii=False)
        with contextlib.suppress(RuntimeError):  # loop shutting down
            self._loop.call_soon_threadsafe(self._fanout, event, payload)

    def _fanout(self, event: str, payload: str) -> None:
        for q in list(self._subscribers):
            if q.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    q.get_nowait()
            q.put_nowait((event, payload))


broker = Broker()
