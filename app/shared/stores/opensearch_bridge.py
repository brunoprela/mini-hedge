"""Bridge EventBus events to OpenSearch for full-text audit search.

Subscribes to the same fund-scoped Kafka topics as AuditBridge and
ImmudbBridge, but writes to OpenSearch for search-optimized access.

Three independent Kafka consumers — no dual-write risk:
  - AuditBridge → PostgreSQL (source of truth, hash-chained)
  - ImmudbBridge → immudb (tamper-proof witness)
  - OpenSearchBridge → OpenSearch (search index)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.shared.schema_registry import fund_audit_topics_for_slug

if TYPE_CHECKING:
    from app.shared.events import BaseEvent, EventBus, EventHandler
    from app.shared.stores.opensearch_client import OpenSearchClient

logger = structlog.get_logger()


class OpenSearchBridge:
    """Forwards all fund-scoped events to OpenSearch for audit search."""

    def __init__(self, client: OpenSearchClient) -> None:
        self._client = client
        self._events_indexed = 0

    @property
    def events_indexed(self) -> int:
        return self._events_indexed

    def wire(self, event_bus: EventBus, fund_slugs: list[str]) -> None:
        """Subscribe to all fund-scoped topics for OpenSearch indexing."""
        for slug in fund_slugs:
            for topic in fund_audit_topics_for_slug(slug):
                event_bus.subscribe(topic, self._make_handler())

        logger.info(
            "opensearch_bridge_wired",
            fund_slugs=fund_slugs,
        )

    def _make_handler(self) -> EventHandler:
        """Create an event handler that indexes to OpenSearch."""

        async def handler(event: BaseEvent) -> None:
            try:
                await self._client.index_event(
                    event_id=event.event_id,
                    event_type=event.event_type,
                    event_version=event.event_version,
                    timestamp=event.timestamp.isoformat(),
                    actor_id=event.actor_id,
                    actor_type=event.actor_type,
                    fund_slug=event.fund_slug,
                    data=event.data,
                )
                self._events_indexed += 1
            except Exception:
                logger.exception(
                    "opensearch_bridge_index_failed",
                    event_id=event.event_id,
                    event_type=event.event_type,
                )

        return handler
