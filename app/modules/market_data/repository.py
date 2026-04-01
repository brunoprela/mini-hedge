"""Data access for the market_data schema."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.market_data.models import PriceRecord


class PriceRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_latest(self, instrument_id: str) -> PriceRecord | None:
        async with self._session_factory() as session:
            stmt = (
                select(PriceRecord)
                .where(PriceRecord.instrument_id == instrument_id)
                .order_by(PriceRecord.timestamp.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_history(
        self,
        instrument_id: str,
        start: datetime,
        end: datetime,
    ) -> list[PriceRecord]:
        async with self._session_factory() as session:
            stmt = (
                select(PriceRecord)
                .where(
                    PriceRecord.instrument_id == instrument_id,
                    PriceRecord.timestamp >= start,
                    PriceRecord.timestamp <= end,
                )
                .order_by(PriceRecord.timestamp)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def insert(self, record: PriceRecord) -> None:
        async with self._session_factory() as session:
            stmt = (
                pg_insert(PriceRecord)
                .values(
                    timestamp=record.timestamp,
                    instrument_id=record.instrument_id,
                    bid=record.bid,
                    ask=record.ask,
                    mid=record.mid,
                    volume=record.volume,
                    source=record.source,
                )
                .on_conflict_do_nothing(
                    index_elements=["timestamp", "instrument_id"],
                )
            )
            await session.execute(stmt)
            await session.commit()
