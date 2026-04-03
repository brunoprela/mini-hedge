"""Data access for audit log records."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.modules.platform.models import AuditLogRecord

if TYPE_CHECKING:
    from app.shared.database import TenantSessionFactory
    from app.shared.events import BaseEvent

logger = structlog.get_logger()


class AuditLogRepository:
    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._session_factory = session_factory

    async def insert(self, event: BaseEvent) -> None:
        """Persist an event to the audit log. Idempotent via unique event_id."""
        async with self._session_factory() as session:
            stmt = insert(AuditLogRecord).values(
                event_id=event.event_id,
                event_type=event.event_type,
                actor_id=event.actor_id,
                actor_type=event.actor_type,
                fund_slug=event.fund_slug,
                payload=_safe_payload(event),
            )
            stmt = stmt.on_conflict_do_nothing(index_elements=["event_id"])
            await session.execute(stmt)
            await session.commit()

    async def insert_admin_event(
        self,
        *,
        event_type: str,
        actor_id: str,
        actor_type: str,
        fund_slug: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Insert an admin audit event directly (no BaseEvent required)."""
        async with self._session_factory() as session:
            record = AuditLogRecord(
                event_id=f"admin-{uuid4().hex}",
                event_type=event_type,
                actor_id=actor_id,
                actor_type=actor_type,
                fund_slug=fund_slug,
                payload=payload or {},
            )
            session.add(record)
            await session.commit()

    async def query(
        self,
        *,
        fund_slug: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditLogRecord], int]:
        """Query audit log with optional filters.

        Returns ``(records, total_count)`` for pagination.
        """
        async with self._session_factory() as session:
            # Base filter
            conditions = []
            if fund_slug:
                conditions.append(AuditLogRecord.fund_slug == fund_slug)
            if event_type:
                conditions.append(AuditLogRecord.event_type == event_type)

            # Total count
            count_stmt = select(func.count(AuditLogRecord.id))
            for cond in conditions:
                count_stmt = count_stmt.where(cond)
            total = (await session.execute(count_stmt)).scalar_one()

            # Page
            stmt = select(AuditLogRecord).order_by(
                AuditLogRecord.created_at.desc()
            )
            for cond in conditions:
                stmt = stmt.where(cond)
            stmt = stmt.offset(offset).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all()), total


def _safe_payload(event: BaseEvent) -> dict[str, Any]:
    """Build a JSON-safe payload dict from the event."""
    return {
        "data": event.data,
        "event_version": event.event_version,
        "timestamp": event.timestamp.isoformat(),
    }
