"""Volatility surface data persistence."""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.market_data.models.volatility_surface import VolatilitySurfaceRecord
from app.shared.repository import BaseRepository


class VolatilitySurfaceRepository(BaseRepository):
    async def get_surface(
        self,
        instrument_id: str,
        expiry: date,
        *,
        session: AsyncSession | None = None,
    ) -> list[VolatilitySurfaceRecord]:
        """Get all strike/vol points for an instrument and expiry."""
        async with self._session(session) as session:
            stmt = (
                select(VolatilitySurfaceRecord)
                .where(
                    VolatilitySurfaceRecord.instrument_id == instrument_id,
                    VolatilitySurfaceRecord.expiry == expiry,
                )
                .order_by(VolatilitySurfaceRecord.strike)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_latest_surface(
        self,
        instrument_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[VolatilitySurfaceRecord]:
        """Get the most recent surface snapshot for an instrument (all expiries)."""
        async with self._session(session) as session:
            # Find the latest timestamp for this instrument
            latest_ts_stmt = (
                select(VolatilitySurfaceRecord.timestamp)
                .where(VolatilitySurfaceRecord.instrument_id == instrument_id)
                .order_by(VolatilitySurfaceRecord.timestamp.desc())
                .limit(1)
            )
            ts_result = await session.execute(latest_ts_stmt)
            latest_ts = ts_result.scalar_one_or_none()
            if latest_ts is None:
                return []

            stmt = (
                select(VolatilitySurfaceRecord)
                .where(
                    VolatilitySurfaceRecord.instrument_id == instrument_id,
                    VolatilitySurfaceRecord.timestamp == latest_ts,
                )
                .order_by(VolatilitySurfaceRecord.expiry, VolatilitySurfaceRecord.strike)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_expiries(
        self,
        instrument_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[date]:
        """Get all available expiry dates for an instrument."""
        async with self._session(session) as session:
            stmt = (
                select(VolatilitySurfaceRecord.expiry)
                .where(VolatilitySurfaceRecord.instrument_id == instrument_id)
                .distinct()
                .order_by(VolatilitySurfaceRecord.expiry)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def insert(
        self,
        record: VolatilitySurfaceRecord,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as session:
            stmt = (
                pg_insert(VolatilitySurfaceRecord)
                .values(
                    timestamp=record.timestamp,
                    instrument_id=record.instrument_id,
                    expiry=record.expiry,
                    strike=record.strike,
                    implied_vol=record.implied_vol,
                    delta=record.delta,
                    source=record.source,
                )
                .on_conflict_do_nothing(
                    index_elements=["timestamp", "instrument_id", "expiry", "strike"],
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def insert_batch(
        self,
        records: list[VolatilitySurfaceRecord],
        *,
        session: AsyncSession | None = None,
    ) -> None:
        """Insert a batch of vol surface points."""
        async with self._session(session) as session:
            for record in records:
                stmt = (
                    pg_insert(VolatilitySurfaceRecord)
                    .values(
                        timestamp=record.timestamp,
                        instrument_id=record.instrument_id,
                        expiry=record.expiry,
                        strike=record.strike,
                        implied_vol=record.implied_vol,
                        delta=record.delta,
                        source=record.source,
                    )
                    .on_conflict_do_nothing(
                        index_elements=["timestamp", "instrument_id", "expiry", "strike"],
                    )
                )
                await session.execute(stmt)
            await session.commit()
