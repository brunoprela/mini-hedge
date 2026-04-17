"""Reconciliation break persistence."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.eod.models.reconciliation_break import ReconciliationBreakRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ReconciliationBreakRepository(BaseRepository):
    """Data access for tracked reconciliation breaks."""

    async def insert(
        self,
        record: ReconciliationBreakRecord,
        *,
        session: AsyncSession | None = None,
    ) -> ReconciliationBreakRecord:
        async with self._session(session) as s:
            s.add(record)
            await s.commit()
            await s.refresh(record)
            return record

    async def insert_batch(
        self,
        records: list[ReconciliationBreakRecord],
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as s:
            s.add_all(records)
            await s.commit()

    async def get_by_id(
        self,
        break_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> ReconciliationBreakRecord | None:
        async with self._session(session) as s:
            stmt = select(ReconciliationBreakRecord).where(
                ReconciliationBreakRecord.id == break_id,
            )
            result = await s.execute(stmt)
            return result.scalar_one_or_none()

    async def list_by_portfolio_date(
        self,
        portfolio_id: str,
        business_date: date,
        *,
        session: AsyncSession | None = None,
    ) -> list[ReconciliationBreakRecord]:
        async with self._session(session) as s:
            stmt = (
                select(ReconciliationBreakRecord)
                .where(
                    ReconciliationBreakRecord.portfolio_id == portfolio_id,
                    ReconciliationBreakRecord.business_date == business_date,
                )
                .order_by(ReconciliationBreakRecord.created_at)
            )
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def list_open(
        self,
        portfolio_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[ReconciliationBreakRecord]:
        async with self._session(session) as s:
            stmt = (
                select(ReconciliationBreakRecord)
                .where(
                    ReconciliationBreakRecord.portfolio_id == portfolio_id,
                    ReconciliationBreakRecord.status.in_(["open", "investigating", "escalated"]),
                )
                .order_by(ReconciliationBreakRecord.created_at)
            )
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def list_recently_resolved(
        self,
        portfolio_id: str,
        *,
        since: date,
        session: AsyncSession | None = None,
    ) -> list[ReconciliationBreakRecord]:
        async with self._session(session) as s:
            stmt = (
                select(ReconciliationBreakRecord)
                .where(
                    ReconciliationBreakRecord.portfolio_id == portfolio_id,
                    ReconciliationBreakRecord.status == "resolved",
                    ReconciliationBreakRecord.business_date >= since,
                )
                .order_by(ReconciliationBreakRecord.created_at.desc())
            )
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def update_status(
        self,
        break_id: str,
        *,
        status: str,
        assigned_to: str | None = None,
        resolution_note: str | None = None,
        resolved_at: datetime | None = None,
        session: AsyncSession | None = None,
    ) -> ReconciliationBreakRecord | None:
        async with self._session(session) as s:
            stmt = select(ReconciliationBreakRecord).where(
                ReconciliationBreakRecord.id == break_id,
            )
            result = await s.execute(stmt)
            record = result.scalar_one_or_none()
            if record is None:
                return None

            record.status = status
            if assigned_to is not None:
                record.assigned_to = assigned_to
            if resolution_note is not None:
                record.resolution_note = resolution_note
            if resolved_at is not None:
                record.resolved_at = resolved_at
            await s.commit()
            await s.refresh(record)
            return record
