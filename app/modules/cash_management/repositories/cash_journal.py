"""Cash journal persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.cash_management.models.cash_journal import CashJournalRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CashJournalRepository(BaseRepository):
    async def insert(
        self, record: CashJournalRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def get_by_portfolio(
        self,
        portfolio_id: UUID,
        limit: int = 100,
        *,
        session: AsyncSession | None = None,
    ) -> list[CashJournalRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(CashJournalRecord)
                .where(CashJournalRecord.portfolio_id == str(portfolio_id))
                .order_by(CashJournalRecord.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
