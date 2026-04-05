"""Data access for portfolio records."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.models import PortfolioRecord
from app.shared.repository import BaseRepository


class PortfolioRepository(BaseRepository):
    async def get_by_fund(
        self, fund_id: str, *, session: AsyncSession | None = None
    ) -> list[PortfolioRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(PortfolioRecord).where(
                    PortfolioRecord.fund_id == fund_id,
                    PortfolioRecord.is_active.is_(True),
                )
            )
            return list(result.scalars().all())

    async def get_by_id(
        self, portfolio_id: UUID, *, session: AsyncSession | None = None
    ) -> PortfolioRecord | None:
        async with self._session(session) as session:
            result = await session.execute(
                select(PortfolioRecord).where(PortfolioRecord.id == str(portfolio_id))
            )
            return result.scalar_one_or_none()

    async def insert(self, record: PortfolioRecord, *, session: AsyncSession | None = None) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def insert_batch(
        self, records: list[PortfolioRecord], *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add_all(records)
            await session.commit()
