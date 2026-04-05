"""Redis-backed idempotency key middleware — prevents duplicate mutations.

Pure ASGI implementation (no BaseHTTPMiddleware) consistent with the rest
of the middleware stack.

Flow:
1. Client sends ``Idempotency-Key: <uuid>`` header on POST/PUT/DELETE/PATCH.
2. Middleware checks Redis for the key.
3. If found → return the cached response (status + body). No handler runs.
4. If not found → acquire a processing lock (SET NX), run the handler,
   cache the response with a 24-hour TTL, then return it.
5. If another request is already processing the same key → 409 Conflict.
6. If no header is present on a mutation → proceed normally (opt-in).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from starlette.types import ASGIApp, Receive, Scope, Send

logger = structlog.get_logger()

_MUTATION_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
_KEY_PREFIX = "idempotency:"
_LOCK_SUFFIX = ":lock"
_TTL_SECONDS = 60 * 60 * 24  # 24 hours
_LOCK_TTL_SECONDS = 60  # 1 minute — guards against crashed handlers


class IdempotencyMiddleware:
    """Pure ASGI middleware that enforces idempotency via Redis."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        if method not in _MUTATION_METHODS:
            await self.app(scope, receive, send)
            return

        # Extract Idempotency-Key header
        idem_key = _get_header(scope, b"idempotency-key")
        if idem_key is None:
            # No header → opt-in; proceed normally
            await self.app(scope, receive, send)
            return

        # Redis may not be available (disabled in settings)
        redis: Redis | None = getattr(scope["app"].state, "redis", None)
        if redis is None:
            await self.app(scope, receive, send)
            return

        cache_key = f"{_KEY_PREFIX}{idem_key}"
        lock_key = f"{cache_key}{_LOCK_SUFFIX}"

        # 1. Check for a cached response
        cached = await redis.get(cache_key)
        if cached is not None:
            logger.info("idempotency_cache_hit", idempotency_key=idem_key)
            data = json.loads(cached)
            await _send_raw(send, data["status"], data["body"], data["content_type"])
            return

        # 2. Try to acquire processing lock (SET NX with short TTL)
        acquired = await redis.set(lock_key, "1", nx=True, ex=_LOCK_TTL_SECONDS)
        if not acquired:
            logger.warning("idempotency_conflict", idempotency_key=idem_key)
            await _send_raw(
                send,
                409,
                json.dumps({"detail": "Idempotency key is already being processed"}),
                "application/json",
            )
            return

        # 3. Execute the handler and capture the response
        try:
            captured = _ResponseCapture(send)
            await self.app(scope, receive, captured)

            # Cache the result
            payload = json.dumps(
                {
                    "status": captured.status_code,
                    "body": captured.body_text,
                    "content_type": captured.content_type,
                }
            )
            await redis.set(cache_key, payload, ex=_TTL_SECONDS)
            logger.info(
                "idempotency_cached",
                idempotency_key=idem_key,
                status=captured.status_code,
            )
        finally:
            # Always release the lock
            await redis.delete(lock_key)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_header(scope: Scope, name: bytes) -> str | None:
    """Return the value of a header (case-insensitive) or None."""
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return value.decode("utf-8")
    return None


async def _send_raw(send: Send, status: int, body: str, content_type: str) -> None:
    """Send a complete HTTP response from cached data."""
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", content_type.encode("utf-8")),
            ],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": body.encode("utf-8"),
        }
    )


class _ResponseCapture:
    """Wraps the ASGI ``send`` callable to capture status, headers, and body."""

    def __init__(self, send: Send) -> None:
        self._send = send
        self.status_code: int = 200
        self.content_type: str = "application/json"
        self.body_text: str = ""

    async def __call__(self, message: dict) -> None:  # type: ignore[override]
        if message["type"] == "http.response.start":
            self.status_code = message.get("status", 200)
            for key, value in message.get("headers", []):
                if key.lower() == b"content-type":
                    self.content_type = value.decode("utf-8")
                    break

        elif message["type"] == "http.response.body":
            raw = message.get("body", b"")
            if raw:
                self.body_text += raw.decode("utf-8", errors="replace")

        # Always forward to the real send so the client still gets the response
        await self._send(message)
