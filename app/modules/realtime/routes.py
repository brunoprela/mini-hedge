"""SSE streaming endpoint — pushes real-time events to browsers via Redis pub/sub.

Authentication is handled by the auth middleware, which extracts the JWT
from the ``token`` query parameter for SSE paths (EventSource API does
not support custom headers).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

import structlog
from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.shared.auth import get_actor_context
from app.shared.redis_bridge import PRICES_CHANNEL, fund_channel

logger = structlog.get_logger()

router = APIRouter(tags=["realtime"])

_HEARTBEAT_INTERVAL = 30  # seconds


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
    token: str = Query(..., description="JWT for authentication (used by middleware)"),
    fund_slug: str | None = Query(None, description="Fund slug override"),
) -> StreamingResponse:
    """SSE endpoint for real-time event streaming.

    The ``token`` query parameter is consumed by the auth middleware —
    by the time we get here, ``RequestContext`` is already set.
    """
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        payload = json.dumps({"error": "Real-time streaming not available"})
        return StreamingResponse(
            iter([f"data: {payload}\n\n"]),
            status_code=503,
            media_type="text/event-stream",
        )

    # Context is set by middleware — use it to determine channels
    request_context = get_actor_context()
    channels = [PRICES_CHANNEL]
    if request_context.fund_slug:
        channels.append(fund_channel(request_context.fund_slug))

    return StreamingResponse(
        _event_stream(request, channels),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
