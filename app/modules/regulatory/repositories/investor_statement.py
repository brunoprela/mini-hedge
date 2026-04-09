"""Investor statement persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.regulatory.models.investor_statement import InvestorStatementRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class InvestorStatementRepository(BaseRepository):
    """CRUD for InvestorStatementRecord."""

    async def save(
        self, record: InvestorStatementRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def list_by_investor(
        self,
        investor_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[InvestorStatementRecord]:
        async with self._session(session) as session:
            stmt = (
                select(InvestorStatementRecord)
                .where(InvestorStatementRecord.investor_id == investor_id)
                .order_by(InvestorStatementRecord.period_end.desc())
                .limit(20)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
