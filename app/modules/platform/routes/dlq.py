"""Admin API routes — DLQ (dead-letter queue) management endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, Request

from app.shared.auth import Permission, require_platform_permission
from app.shared.auth.request_context import RequestContext

router = APIRouter(prefix="/admin", tags=["admin"])


def _get_dlq_manager(request: Request) -> Any:
    """Retrieve the DlqManager from app state."""
    return request.app.state.dlq_manager


@router.get("/dlq")
async def list_dlq_topics(
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_AUDIT_READ),
    dlq_manager: Any = Depends(_get_dlq_manager),
) -> list[dict[str, Any]]:
    """List all DLQ topics with message counts."""
    topics = await dlq_manager.list_topics()
    return [
        {
            "topic": t.topic,
            "source_topic": t.source_topic,
            "message_count": t.message_count,
        }
        for t in topics
    ]


@router.get("/dlq/{topic}")
async def peek_dlq_topic(
    topic: str,
    limit: int = 10,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_AUDIT_READ),
    dlq_manager: Any = Depends(_get_dlq_manager),
) -> list[dict[str, Any]]:
    """Peek at messages in a DLQ topic without consuming them."""
    messages = await dlq_manager.peek(topic, limit=limit)
    return [
        {
            "offset": m.offset,
            "timestamp": m.timestamp,
            "key": m.key,
            "value": m.value,
        }
        for m in messages
    ]


@router.post("/dlq/{topic}/replay")
async def replay_dlq_topic(
    topic: str,
    limit: int = 100,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_AUDIT_READ),
    dlq_manager: Any = Depends(_get_dlq_manager),
) -> dict[str, Any]:
    """Replay DLQ messages back to the source topic."""
    result = await dlq_manager.replay(topic, limit=limit)
    return {
        "topic": result.topic,
        "source_topic": result.source_topic,
        "replayed": result.replayed,
        "failed": result.failed,
    }
