"""Regulatory filing persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.regulatory.models.regulatory_filing import RegulatoryFilingRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class RegulatoryFilingRepository(BaseRepository):
    """CRUD for RegulatoryFilingRecord."""

    async def insert(
        self, record: RegulatoryFilingRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def list_all(
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

    async def get_by_id(
        self, filing_id: str, *, session: AsyncSession | None = None
    ) -> RegulatoryFilingRecord | None:
        async with self._session(session) as session:
            result = await session.execute(
                select(RegulatoryFilingRecord).where(RegulatoryFilingRecord.id == filing_id)
            )
            return result.scalar_one_or_none()
