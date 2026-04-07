"""Data access for the market_data schema."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.market_data.models import FXRateRecord, PriceRecord
from app.shared.repository import BaseRepository


class PriceRepository(BaseRepository):
    async def get_latest(
        self, instrument_id: str, *, session: AsyncSession | None = None
    ) -> PriceRecord | None:
        async with self._session(session) as session:
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
        *,
        session: AsyncSession | None = None,
    ) -> list[PriceRecord]:
        async with self._session(session) as session:
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

    async def insert(self, record: PriceRecord, *, session: AsyncSession | None = None) -> None:
        async with self._session(session) as session:
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


class FXRateRepository(BaseRepository):
    """Data access for FX spot rates."""

    async def get_latest(
        self,
        base_currency: str,
        quote_currency: str,
        *,
        session: AsyncSession | None = None,
    ) -> FXRateRecord | None:
        async with self._session(session) as session:
            stmt = (
                select(FXRateRecord)
                .where(
                    FXRateRecord.base_currency == base_currency,
                    FXRateRecord.quote_currency == quote_currency,
                )
                .order_by(FXRateRecord.timestamp.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_latest_all(self, *, session: AsyncSession | None = None) -> list[FXRateRecord]:
        """Get the most recent rate for each currency pair."""
        from sqlalchemy import func

        async with self._session(session) as session:
            sub = (
                select(
                    FXRateRecord.base_currency,
                    FXRateRecord.quote_currency,
                    func.max(FXRateRecord.timestamp).label("max_ts"),
                )
                .group_by(FXRateRecord.base_currency, FXRateRecord.quote_currency)
                .subquery()
            )
            stmt = select(FXRateRecord).join(
                sub,
                (FXRateRecord.base_currency == sub.c.base_currency)
                & (FXRateRecord.quote_currency == sub.c.quote_currency)
                & (FXRateRecord.timestamp == sub.c.max_ts),
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_history(
        self,
        base_currency: str,
        quote_currency: str,
        start: datetime,
        end: datetime,
        *,
        session: AsyncSession | None = None,
    ) -> list[FXRateRecord]:
        async with self._session(session) as session:
            stmt = (
                select(FXRateRecord)
                .where(
                    FXRateRecord.base_currency == base_currency,
                    FXRateRecord.quote_currency == quote_currency,
                    FXRateRecord.timestamp >= start,
                    FXRateRecord.timestamp <= end,
                )
                .order_by(FXRateRecord.timestamp)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def insert(self, record: FXRateRecord, *, session: AsyncSession | None = None) -> None:
        async with self._session(session) as session:
            stmt = (
                pg_insert(FXRateRecord)
                .values(
                    timestamp=record.timestamp,
                    base_currency=record.base_currency,
                    quote_currency=record.quote_currency,
                    rate=record.rate,
                    source=record.source,
                )
                .on_conflict_do_nothing(
                    index_elements=["timestamp", "base_currency", "quote_currency"],
                )
            )
            await session.execute(stmt)
            await session.commit()
