"""Data access for platform schema — funds and portfolios."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.platform.models import FundRecord, PortfolioRecord


class FundRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_slug(self, slug: str) -> FundRecord | None:
        async with self._session_factory() as session:
            result = await session.execute(select(FundRecord).where(FundRecord.slug == slug))
            return result.scalar_one_or_none()

    async def get_all_active(self) -> list[FundRecord]:
        async with self._session_factory() as session:
            result = await session.execute(select(FundRecord).where(FundRecord.status == "active"))
            return list(result.scalars().all())

    async def insert(self, record: FundRecord) -> None:
        async with self._session_factory() as session:
            session.add(record)
            await session.commit()


class PortfolioRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_fund(self, fund_id: str) -> list[PortfolioRecord]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(PortfolioRecord).where(
                    PortfolioRecord.fund_id == fund_id,
                    PortfolioRecord.is_active.is_(True),
                )
            )
            return list(result.scalars().all())

    async def get_by_id(self, portfolio_id: UUID) -> PortfolioRecord | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(PortfolioRecord).where(PortfolioRecord.id == str(portfolio_id))
            )
            return result.scalar_one_or_none()

    async def insert(self, record: PortfolioRecord) -> None:
        async with self._session_factory() as session:
            session.add(record)
            await session.commit()

    async def insert_batch(self, records: list[PortfolioRecord]) -> None:
        async with self._session_factory() as session:
            session.add_all(records)
            await session.commit()
