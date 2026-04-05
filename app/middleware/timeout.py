"""Request timeout middleware — prevents stuck workers.

Pure ASGI implementation that wraps each HTTP request in an
``asyncio.timeout`` context. SSE/streaming endpoints get a longer
timeout since they are long-lived by design.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

logger = structlog.get_logger()

# Paths that get extended timeouts (long-lived connections)
_STREAMING_PATHS = {"/api/v1/stream/events"}

_DEFAULT_TIMEOUT = 30  # seconds — regular API requests
_STREAMING_TIMEOUT = 3600  # seconds — SSE streams (1 hour)


class TimeoutMiddleware:
    """Pure ASGI middleware that enforces per-request timeouts."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        default_timeout: float = _DEFAULT_TIMEOUT,
        streaming_timeout: float = _STREAMING_TIMEOUT,
    ) -> None:
        self.app = app
        self._default_timeout = default_timeout
        self._streaming_timeout = streaming_timeout

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope["path"]
        timeout = self._streaming_timeout if path in _STREAMING_PATHS else self._default_timeout

        try:
            async with asyncio.timeout(timeout):
                await self.app(scope, receive, send)
        except TimeoutError:
            logger.warning("request_timeout", path=path, timeout_s=timeout)
            # Send 504 Gateway Timeout
            await send(
                {
                    "type": "http.response.start",
                    "status": 504,
                    "headers": [
                        (b"content-type", b"application/json"),
                    ],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b'{"detail":"Request timed out"}',
                }
            )
