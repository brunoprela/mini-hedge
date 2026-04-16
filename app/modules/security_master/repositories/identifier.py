"""Data access for instrument identifiers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.security_master.models.identifier import InstrumentIdentifierRecord
from app.modules.security_master.models.instrument import InstrumentRecord
from app.shared.repository import BaseRepository


class IdentifierRepository(BaseRepository):
    async def resolve(
        self,
        id_type: str,
        id_value: str,
        *,
        session: AsyncSession | None = None,
    ) -> InstrumentRecord | None:
        """Look up a canonical instrument by any identifier type/value pair."""
        async with self._session(session) as session:
            stmt = (
                select(InstrumentRecord)
                .join(
                    InstrumentIdentifierRecord,
                    InstrumentIdentifierRecord.instrument_id == InstrumentRecord.id,
                )
                .where(
                    InstrumentIdentifierRecord.id_type == id_type,
                    InstrumentIdentifierRecord.id_value == id_value.upper(),
                    InstrumentRecord.is_active.is_(True),
                )
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_identifiers(
        self,
        instrument_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[InstrumentIdentifierRecord]:
        """Get all identifiers for a given instrument."""
        async with self._session(session) as session:
            stmt = (
                select(InstrumentIdentifierRecord)
                .where(InstrumentIdentifierRecord.instrument_id == instrument_id)
                .order_by(InstrumentIdentifierRecord.id_type)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def upsert(
        self,
        instrument_id: str,
        id_type: str,
        id_value: str,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        """Add or update an identifier mapping."""
        async with self._session(session) as session:
            # Check if exists
            stmt = select(InstrumentIdentifierRecord).where(
                InstrumentIdentifierRecord.id_type == id_type,
                InstrumentIdentifierRecord.id_value == id_value.upper(),
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                existing.instrument_id = instrument_id
            else:
                session.add(
                    InstrumentIdentifierRecord(
                        instrument_id=instrument_id,
                        id_type=id_type,
                        id_value=id_value.upper(),
                    )
                )
            await session.commit()
