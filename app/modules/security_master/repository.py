"""Data access for the security_master schema."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.security_master.interface import AssetClass
from app.modules.security_master.models import InstrumentRecord


class InstrumentRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_id(self, instrument_id: UUID) -> InstrumentRecord | None:
        async with self._session_factory() as session:
            stmt = select(InstrumentRecord).where(InstrumentRecord.id == str(instrument_id))
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_ticker(self, ticker: str) -> InstrumentRecord | None:
        async with self._session_factory() as session:
            stmt = select(InstrumentRecord).where(InstrumentRecord.ticker == ticker.upper())
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_all_active(
        self,
        asset_class: AssetClass | None = None,
    ) -> list[InstrumentRecord]:
        async with self._session_factory() as session:
            stmt = select(InstrumentRecord).where(InstrumentRecord.is_active.is_(True))
            if asset_class is not None:
                stmt = stmt.where(InstrumentRecord.asset_class == asset_class.value)
            stmt = stmt.order_by(InstrumentRecord.ticker)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def search(self, query: str, limit: int = 20) -> list[InstrumentRecord]:
        async with self._session_factory() as session:
            pattern = f"%{query}%"
            stmt = (
                select(InstrumentRecord)
                .where(
                    InstrumentRecord.name.ilike(pattern) | InstrumentRecord.ticker.ilike(pattern)
                )
                .limit(limit)
                .order_by(InstrumentRecord.ticker)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def insert_batch(self, records: list[InstrumentRecord]) -> None:
        async with self._session_factory() as session:
            session.add_all(records)
            await session.commit()
