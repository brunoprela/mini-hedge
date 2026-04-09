"""Scheduled flow persistence."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.cash_management.models.scheduled_flow import ScheduledFlowRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ScheduledFlowRepository(BaseRepository):
    async def insert(
        self, record: ScheduledFlowRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def get_by_portfolio(
        self,
        portfolio_id: UUID,
        start: date,
        end: date,
        *,
        session: AsyncSession | None = None,
    ) -> list[ScheduledFlowRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(ScheduledFlowRecord)
                .where(
                    ScheduledFlowRecord.portfolio_id == str(portfolio_id),
                    ScheduledFlowRecord.flow_date >= start,
                    ScheduledFlowRecord.flow_date <= end,
                )
                .order_by(ScheduledFlowRecord.flow_date.asc())
            )
            return list(result.scalars().all())
