"""Bridge EventBus events to immudb for tamper-proof audit witness.

Subscribes to the same fund-scoped Kafka topics as AuditBridge, but
writes to immudb instead of PostgreSQL.  This creates an independent
cryptographic witness: if someone tampers with PostgreSQL records,
the immudb copy provides verifiable proof of the original event.

Two independent Kafka consumers — no dual-write risk.  If immudb is
down, this consumer falls behind but catches up when it recovers.
Kafka handles the delivery guarantee.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.shared.schema_registry import fund_audit_topics_for_slug

if TYPE_CHECKING:
    from app.shared.events import BaseEvent, EventBus, EventHandler
    from app.shared.stores.immudb_client import ImmudbClient

logger = structlog.get_logger()


class ImmudbBridge:
    """Forwards all fund-scoped events to immudb for immutable storage."""

    def __init__(self, client: ImmudbClient) -> None:
        self._client = client
        self._events_written = 0

    @property
    def events_written(self) -> int:
        return self._events_written

    def wire(self, event_bus: EventBus, fund_slugs: list[str]) -> None:
        """Subscribe to all fund-scoped topics for immudb persistence."""
        for slug in fund_slugs:
            for topic in fund_audit_topics_for_slug(slug):
                event_bus.subscribe(topic, self._make_handler())

        logger.info(
            "immudb_bridge_wired",
            fund_slugs=fund_slugs,
        )

    def _make_handler(self) -> EventHandler:
        """Create an event handler that persists to immudb."""

        async def handler(event: BaseEvent) -> None:
            try:
                await self._client.verified_set(
                    key=f"audit:{event.event_id}",
                    value={
                        "event_id": event.event_id,
                        "event_type": event.event_type,
                        "event_version": event.event_version,
                        "timestamp": event.timestamp.isoformat(),
                        "actor_id": event.actor_id,
                        "actor_type": event.actor_type,
                        "fund_slug": event.fund_slug,
                        "data": event.data,
                    },
                )
                self._events_written += 1
            except Exception:
                logger.exception(
                    "immudb_bridge_write_failed",
                    event_id=event.event_id,
                    event_type=event.event_type,
                )

        return handler
