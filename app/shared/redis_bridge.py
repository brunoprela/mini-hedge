"""Bridge EventBus events to Redis pub/sub for SSE streaming.

Subscribes to all relevant EventBus topics and republishes each event
as JSON on Redis channels. SSE endpoints then subscribe to these Redis
channels to push real-time updates to browsers.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import structlog

from app.shared.schema_registry import fund_topics_for_slug, shared_topics

if TYPE_CHECKING:
    import redis.asyncio as aioredis

    from app.shared.events import BaseEvent, EventBus

logger = structlog.get_logger()

# Redis channel names
PRICES_CHANNEL = "shared:prices"


def fund_channel(fund_slug: str) -> str:
    """Redis channel for a fund's events: ``fund:{slug}:events``."""
    return f"fund:{fund_slug}:events"


def _event_to_json(event: BaseEvent, channel: str) -> str:
    """Serialize an event to JSON for Redis pub/sub."""
    return json.dumps(
        {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "data": event.data,
            "timestamp": event.timestamp.isoformat(),
            "fund_slug": event.fund_slug,
            "actor_id": event.actor_id,
            "channel": channel,
        }
    )


class RedisBridge:
    """Forwards EventBus events to Redis pub/sub channels."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    def wire(self, event_bus: EventBus, fund_slugs: list[str]) -> None:
        """Subscribe to all EventBus topics and bridge to Redis channels."""
        # Shared topics → shared:prices channel
        for topic in shared_topics():
            event_bus.subscribe(topic, self._make_handler(PRICES_CHANNEL))

        # Fund-scoped topics → fund:{slug}:events channel
        for slug in fund_slugs:
            channel = fund_channel(slug)
            for topic in fund_topics_for_slug(slug):
                event_bus.subscribe(topic, self._make_handler(channel))

        logger.info(
            "redis_bridge_wired",
            shared_topics=len(shared_topics()),
            fund_slugs=fund_slugs,
        )

    def _make_handler(self, channel: str):  # type: ignore[no-untyped-def]
        """Create an event handler that publishes to the given Redis channel."""

        async def handler(event: BaseEvent) -> None:
            payload = _event_to_json(event, channel)
            await self._redis.publish(channel, payload)

        return handler
