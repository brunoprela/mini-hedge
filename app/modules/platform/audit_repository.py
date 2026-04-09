"""Data access for audit log records."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.modules.platform.models import AuditLogRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.shared.audit.events import AuditEventType
    from app.shared.events import BaseEvent

logger = structlog.get_logger()


def _compute_hash(payload_str: str, prev_hash: str) -> str:
    """Compute SHA-256 hex digest of ``payload_str || prev_hash``."""
    return hashlib.sha256((payload_str + prev_hash).encode()).hexdigest()


class AuditLogRepository(BaseRepository):
    async def _fetch_last_hash(self, session: AsyncSession) -> str:
        """Return the ``entry_hash`` of the most recent audit record, or ``""``."""
        stmt = select(AuditLogRecord.entry_hash).order_by(AuditLogRecord.created_at.desc()).limit(1)
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        return row or ""

    async def insert(self, event: BaseEvent, *, session: AsyncSession | None = None) -> None:
        """Persist an event to the audit log. Idempotent via unique event_id."""
        async with self._session(session) as session:
            payload = _safe_payload(event)
            prev_hash = await self._fetch_last_hash(session)
            entry_hash = _compute_hash(json.dumps(payload, sort_keys=True), prev_hash)

            stmt = insert(AuditLogRecord).values(
                event_id=event.event_id,
                event_type=event.event_type,
                actor_id=event.actor_id,
                actor_type=event.actor_type,
                fund_slug=event.fund_slug,
                payload=payload,
                prev_hash=prev_hash or None,
                entry_hash=entry_hash,
            )
            stmt = stmt.on_conflict_do_nothing(index_elements=["event_id"])
            await session.execute(stmt)
            await session.commit()

    async def insert_admin_event(
        self,
        *,
        event_type: AuditEventType,
        actor_id: str,
        actor_type: str,
        fund_slug: str | None = None,
        payload: dict[str, Any] | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        """Insert an admin audit event directly (no BaseEvent required)."""
        async with self._session(session) as session:
            effective_payload = payload or {}
            prev_hash = await self._fetch_last_hash(session)
            entry_hash = _compute_hash(json.dumps(effective_payload, sort_keys=True), prev_hash)

            record = AuditLogRecord(
                event_id=f"admin-{uuid4().hex}",
                event_type=event_type,
                actor_id=actor_id,
                actor_type=actor_type,
                fund_slug=fund_slug,
                payload=effective_payload,
                prev_hash=prev_hash or None,
                entry_hash=entry_hash,
            )
            session.add(record)
            await session.commit()

    async def insert_cdc_event(
        self,
        *,
        event_type: str,
        actor_id: str,
        actor_type: str,
        fund_slug: str | None = None,
        payload: dict[str, Any] | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        """Insert a CDC audit event with a free-form event_type string.

        CDC event types are dynamically derived from table names and operations
        (e.g. ``cdc.orders.insert``) and intentionally bypass the
        :class:`~app.shared.audit_events.AuditEventType` enum.
        """
        async with self._session(session) as session:
            effective_payload = payload or {}
            prev_hash = await self._fetch_last_hash(session)
            entry_hash = _compute_hash(json.dumps(effective_payload, sort_keys=True), prev_hash)

            record = AuditLogRecord(
                event_id=f"cdc-{uuid4().hex}",
                event_type=event_type,
                actor_id=actor_id,
                actor_type=actor_type,
                fund_slug=fund_slug,
                payload=effective_payload,
                prev_hash=prev_hash or None,
                entry_hash=entry_hash,
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
        session: AsyncSession | None = None,
    ) -> tuple[list[AuditLogRecord], int]:
        """Query audit log with optional filters.

        Returns ``(records, total_count)`` for pagination.
        """
        async with self._session(session) as session:
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
            stmt = select(AuditLogRecord).order_by(AuditLogRecord.created_at.desc())
            for cond in conditions:
                stmt = stmt.where(cond)
            stmt = stmt.offset(offset).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all()), total

    async def get_records_for_period(
        self,
        *,
        start: datetime,
        end: datetime,
        fund_slug: str | None = None,
        batch_size: int = 5000,
        session: AsyncSession | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch audit records in a date range as plain dicts (for archival).

        Returns records ordered by created_at ascending. Used by the archival
        service to extract a completed month's records for Parquet export.
        """
        async with self._session(session) as session:
            stmt = (
                select(AuditLogRecord)
                .where(
                    AuditLogRecord.created_at >= start,
                    AuditLogRecord.created_at < end,
                )
                .order_by(AuditLogRecord.created_at.asc())
                .limit(batch_size)
            )
            if fund_slug:
                stmt = stmt.where(AuditLogRecord.fund_slug == fund_slug)

            result = await session.execute(stmt)
            records = result.scalars().all()

            return [
                {
                    "event_id": r.event_id,
                    "event_type": r.event_type,
                    "actor_id": r.actor_id,
                    "actor_type": r.actor_type,
                    "fund_slug": r.fund_slug,
                    "payload": r.payload,
                    "created_at": r.created_at,
                }
                for r in records
            ]

    async def count_for_period(
        self,
        *,
        start: datetime,
        end: datetime,
        fund_slug: str | None = None,
        session: AsyncSession | None = None,
    ) -> int:
        """Count audit records in a date range."""
        async with self._session(session) as session:
            stmt = select(func.count(AuditLogRecord.id)).where(
                AuditLogRecord.created_at >= start,
                AuditLogRecord.created_at < end,
            )
            if fund_slug:
                stmt = stmt.where(AuditLogRecord.fund_slug == fund_slug)
            return (await session.execute(stmt)).scalar_one()


def _safe_payload(event: BaseEvent) -> dict[str, Any]:
    """Build a JSON-safe payload dict from the event."""
    return {
        "data": event.data,
        "event_version": event.event_version,
        "timestamp": event.timestamp.isoformat(),
    }
