"""Data access for the security_master schema."""

from uuid import UUID

from sqlalchemy import select

from app.modules.security_master.interface import AssetClass
from app.modules.security_master.models import EquityExtensionRecord, InstrumentRecord
from app.shared.database import TenantSessionFactory


class InstrumentRepository:
    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._sf = session_factory

    async def get_by_id(self, instrument_id: UUID) -> InstrumentRecord | None:
        async with self._sf() as session:
            stmt = select(InstrumentRecord).where(InstrumentRecord.id == str(instrument_id))
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_ticker(self, ticker: str) -> InstrumentRecord | None:
        async with self._sf() as session:
            stmt = select(InstrumentRecord).where(InstrumentRecord.ticker == ticker.upper())
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_all_active(
        self,
        asset_class: AssetClass | None = None,
    ) -> list[InstrumentRecord]:
        async with self._sf() as session:
            stmt = select(InstrumentRecord).where(InstrumentRecord.is_active.is_(True))
            if asset_class is not None:
                stmt = stmt.where(InstrumentRecord.asset_class == asset_class.value)
            stmt = stmt.order_by(InstrumentRecord.ticker)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def search(
        self, query: str, limit: int = 20, *, offset: int = 0
    ) -> list[InstrumentRecord]:
        async with self._sf() as session:
            pattern = f"%{query}%"
            stmt = (
                select(InstrumentRecord)
                .where(
                    InstrumentRecord.name.ilike(pattern) | InstrumentRecord.ticker.ilike(pattern)
                )
                .order_by(InstrumentRecord.ticker)
                .offset(offset)
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def insert_batch(
        self,
        instruments: list[InstrumentRecord],
        extensions: list[EquityExtensionRecord] | None = None,
    ) -> None:
        """Insert instruments and optional extensions in a single transaction.

        Uses merge semantics so re-seeding doesn't raise on conflict.
        """
        async with self._sf() as session:
            for record in instruments:
                await session.merge(record)
            if extensions:
                for ext in extensions:
                    await session.merge(ext)
            await session.commit()

    async def insert_batch_extensions(self, records: list[EquityExtensionRecord]) -> None:
        """Insert extensions only. Prefer insert_batch() with extensions param."""
        async with self._sf() as session:
            for record in records:
                await session.merge(record)
            await session.commit()
