"""SSE streaming endpoint — pushes real-time events to browsers via Redis pub/sub.

Authentication is via JWT query parameter because the browser's EventSource API
does not support custom headers. The middleware skips this path; auth is handled
inline.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

import structlog
from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.shared.errors import AuthenticationError, AuthorizationError
from app.shared.redis_bridge import PRICES_CHANNEL, fund_channel

logger = structlog.get_logger()

router = APIRouter(tags=["realtime"])

_HEARTBEAT_INTERVAL = 30  # seconds


def _sse_error(message: str, *, status_code: int) -> StreamingResponse:
    """Return a single-event SSE response containing an error."""
    payload = json.dumps({"error": message})
    return StreamingResponse(
        iter([f'data: {payload}\n\n']),
        status_code=status_code,
        media_type="text/event-stream",
    )


async def _event_stream(
    request: Request,
    channels: list[str],
) -> AsyncGenerator[str, None]:
    """Subscribe to Redis pub/sub and yield SSE-formatted events."""
    redis = request.app.state.redis
    pubsub = redis.pubsub()

    await pubsub.subscribe(*channels)
    logger.info("sse_subscribed", channels=channels)

    try:
        while True:
            if await request.is_disconnected():
                break

            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                    timeout=_HEARTBEAT_INTERVAL,
                )
            except TimeoutError:
                # No message within heartbeat interval — send keepalive and continue
                yield ": heartbeat\n\n"
                continue

            if message is not None and message["type"] == "message":
                data = message["data"]
                payload = json.loads(data) if isinstance(data, str) else data
                event_type = payload.get("event_type", "message")
                yield f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"

    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
        logger.info("sse_disconnected", channels=channels)


@router.get("/stream/events")
async def stream_events(
    request: Request,
    token: str = Query(..., description="JWT for authentication"),
    fund_slug: str | None = Query(None, description="Fund slug override"),
) -> StreamingResponse:
    """SSE endpoint for real-time event streaming.

    Authenticates via ``token`` query parameter, subscribes to Redis pub/sub
    channels for the authenticated fund, and streams events as SSE.
    """
    auth_service = getattr(request.app.state, "auth_service", None)
    if auth_service is None:
        return _sse_error("Auth service unavailable", status_code=503)

    try:
        ctx = await auth_service.authenticate_jwt(token, fund_slug=fund_slug)
    except AuthenticationError as exc:
        return _sse_error(exc.message, status_code=401)
    except AuthorizationError as exc:
        return _sse_error(exc.message, status_code=403)

    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        return _sse_error("Real-time streaming not available", status_code=503)

    # Build channel list — always include global prices; add fund channel
    # only if the caller has a fund context (operators may not).
    channels = [PRICES_CHANNEL]
    if ctx.fund_slug:
        channels.append(fund_channel(ctx.fund_slug))

    return StreamingResponse(
        _event_stream(request, channels),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
