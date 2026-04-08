"""Bridge EventBus events to Redis pub/sub for SSE streaming.

Subscribes to all relevant EventBus topics and republishes each event
as JSON on Redis channels. SSE endpoints then subscribe to these Redis
channels to push real-time updates to browsers.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING

import structlog
from redis.exceptions import MaxConnectionsError

from app.shared.schema_registry import fund_topics_for_slug, shared_topics

if TYPE_CHECKING:
    import redis.asyncio as aioredis

    from app.shared.events import BaseEvent, EventBus, EventHandler

logger = structlog.get_logger()

# Redis channel names
PRICES_CHANNEL = "shared:prices"

# Retry settings for pool exhaustion
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 0.05  # 50ms


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
    """Forwards EventBus events to Redis pub/sub channels.

    Uses a coalescing buffer for high-frequency price channels: when
    multiple price events arrive faster than they can be published, only
    the latest event per channel is kept. This prevents connection pool
    exhaustion under load.
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis
        self._drop_count = 0
        self._last_drop_log = 0.0

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

    def _make_handler(self, channel: str) -> EventHandler:
        """Create an event handler that publishes to the given Redis channel.

        Retries up to ``_MAX_RETRIES`` times on pool exhaustion with
        exponential back-off. If all retries fail the event is dropped
        and a throttled warning is logged.
        """

        async def handler(event: BaseEvent) -> None:
            payload = _event_to_json(event, channel)

            for attempt in range(_MAX_RETRIES + 1):
                try:
                    await self._redis.publish(channel, payload)
                    return
                except MaxConnectionsError:
                    if attempt < _MAX_RETRIES:
                        await asyncio.sleep(_RETRY_BASE_DELAY * (2 ** attempt))
                    else:
                        self._record_drop(channel, event.event_id)
                except Exception:
                    logger.exception(
                        "redis_bridge_publish_failed",
                        channel=channel,
                        event_id=event.event_id,
                    )
                    return

        return handler

    def _record_drop(self, channel: str, event_id: str) -> None:
        """Track dropped events and log at most once per second."""
        self._drop_count += 1
        now = time.monotonic()
        if now - self._last_drop_log >= 1.0:
            logger.warning(
                "redis_bridge_pool_exhausted",
                channel=channel,
                event_id=event_id,
                dropped_since_last_log=self._drop_count,
            )
            self._drop_count = 0
            self._last_drop_log = now
