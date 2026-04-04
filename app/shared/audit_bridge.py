"""Bridge EventBus events to the audit log for full event coverage.

Subscribes to all fund-scoped Kafka topics and persists every event
to the audit log table. This ensures 100% event coverage instead of
only auditing trades.executed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.shared.schema_registry import fund_topics_for_slug

if TYPE_CHECKING:
    from app.modules.platform.audit_repository import AuditLogRepository
    from app.shared.events import BaseEvent, EventBus

logger = structlog.get_logger()


class AuditBridge:
    """Forwards all fund-scoped events to the audit log."""

    def __init__(self, audit_repo: AuditLogRepository) -> None:
        self._repo = audit_repo

    def wire(self, event_bus: EventBus, fund_slugs: list[str]) -> None:
        """Subscribe to all fund-scoped topics for audit persistence."""
        for slug in fund_slugs:
            for topic in fund_topics_for_slug(slug):
                event_bus.subscribe(topic, self._make_handler())

        logger.info(
            "audit_bridge_wired",
            fund_slugs=fund_slugs,
        )

    def _make_handler(self):  # type: ignore[no-untyped-def]
        """Create an event handler that persists to the audit log."""

        async def handler(event: BaseEvent) -> None:
            try:
                await self._repo.insert(event)
            except Exception:
                logger.exception(
                    "audit_bridge_insert_failed",
                    event_id=event.event_id,
                    event_type=event.event_type,
                )

        return handler
