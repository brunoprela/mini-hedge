"""Data access for regulatory filings and investor reports."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.regulatory.models import (
    InvestorStatementRecord,
    PerformanceLetterRecord,
    RegulatoryFilingRecord,
)
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class RegulatoryRepository(BaseRepository):
    """CRUD for regulatory filings and investor statements."""

    async def save_filing(
        self, record: RegulatoryFilingRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def list_filings(
        self,
        filing_type: str | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> list[RegulatoryFilingRecord]:
        async with self._session(session) as session:
            stmt = select(RegulatoryFilingRecord).order_by(
                RegulatoryFilingRecord.reporting_period.desc()
            )
            if filing_type:
                stmt = stmt.where(RegulatoryFilingRecord.filing_type == filing_type)
            stmt = stmt.limit(50)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_filing(
        self, filing_id: str, *, session: AsyncSession | None = None
    ) -> RegulatoryFilingRecord | None:
        async with self._session(session) as session:
            result = await session.execute(
                select(RegulatoryFilingRecord).where(RegulatoryFilingRecord.id == filing_id)
            )
            return result.scalar_one_or_none()

    async def save_statement(
        self, record: InvestorStatementRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def list_statements(
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

    async def save_performance_letter(
        self, record: PerformanceLetterRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()
