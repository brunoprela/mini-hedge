"""Data access for the security_master schema."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.security_master.interfaces import AssetClass
from app.modules.security_master.models.equity_extension import EquityExtensionRecord
from app.modules.security_master.models.instrument import InstrumentRecord
from app.shared.repository import BaseRepository

# NOTE: EquityExtensionRecord is still imported here because insert_batch
# accepts extensions as an optional parameter for backward compatibility.


class InstrumentRepository(BaseRepository):
    async def get_by_id(
        self, instrument_id: UUID, *, session: AsyncSession | None = None
    ) -> InstrumentRecord | None:
        async with self._session(session) as session:
            stmt = select(InstrumentRecord).where(InstrumentRecord.id == str(instrument_id))
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_ticker(
        self, ticker: str, *, session: AsyncSession | None = None
    ) -> InstrumentRecord | None:
        async with self._session(session) as session:
            stmt = select(InstrumentRecord).where(InstrumentRecord.ticker == ticker.upper())
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_all_active(
        self,
        asset_class: AssetClass | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> list[InstrumentRecord]:
        async with self._session(session) as session:
            stmt = select(InstrumentRecord).where(InstrumentRecord.is_active.is_(True))
            if asset_class is not None:
                stmt = stmt.where(InstrumentRecord.asset_class == asset_class.value)
            stmt = stmt.order_by(InstrumentRecord.ticker)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def search(
        self,
        query: str,
        limit: int = 20,
        *,
        offset: int = 0,
        session: AsyncSession | None = None,
    ) -> list[InstrumentRecord]:
        async with self._session(session) as session:
            escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
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

    async def insert(
        self,
        record: InstrumentRecord,
        *,
        session: AsyncSession | None = None,
    ) -> InstrumentRecord:
        """Insert a single instrument."""
        async with self._session(session) as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record

    async def update(
        self,
        instrument_id: str,
        updates: dict[str, object],
        *,
        session: AsyncSession | None = None,
    ) -> InstrumentRecord | None:
        """Update an instrument by ID, returning the updated record or None."""
        async with self._session(session) as session:
            stmt = select(InstrumentRecord).where(InstrumentRecord.id == instrument_id)
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            if record is None:
                return None
            for key, value in updates.items():
                if hasattr(record, key):
                    setattr(record, key, value)
            await session.commit()
            await session.refresh(record)
            return record

    async def insert_batch(
        self,
        instruments: list[InstrumentRecord],
        extensions: list[EquityExtensionRecord] | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        """Insert instruments and optional extensions in a single transaction.

        Uses merge semantics so re-seeding doesn't raise on conflict.
        """
        async with self._session(session) as session:
            for record in instruments:
                await session.merge(record)
            if extensions:
                for ext in extensions:
                    await session.merge(ext)
            await session.commit()
