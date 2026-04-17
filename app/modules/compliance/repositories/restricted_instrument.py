"""Data access for restricted instrument records."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, select

from app.modules.compliance.models.restricted_instrument import RestrictedInstrumentRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class RestrictedInstrumentRepository(BaseRepository):
    async def get_by_fund(
        self,
        fund_slug: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[RestrictedInstrumentRecord]:
        """Return all restricted instruments for a fund."""
        async with self._session(session) as session:
            stmt = select(RestrictedInstrumentRecord).where(
                RestrictedInstrumentRecord.fund_slug == fund_slug,
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_instrument_ids(
        self,
        fund_slug: str,
        *,
        session: AsyncSession | None = None,
    ) -> set[str]:
        """Return the set of restricted instrument_ids for a fund."""
        async with self._session(session) as session:
            stmt = select(RestrictedInstrumentRecord.instrument_id).where(
                RestrictedInstrumentRecord.fund_slug == fund_slug,
            )
            result = await session.execute(stmt)
            return {row for row in result.scalars().all()}

    async def insert(
        self,
        *,
        fund_slug: str,
        instrument_id: str,
        reason: str | None = None,
        added_by: str | None = None,
        session: AsyncSession | None = None,
    ) -> RestrictedInstrumentRecord:
        """Add an instrument to the restricted list."""
        async with self._session(session) as session:
            record = RestrictedInstrumentRecord(
                fund_slug=fund_slug,
                instrument_id=instrument_id,
                reason=reason,
                added_by=added_by,
            )
            session.add(record)
            await session.flush()
            return record

    async def delete(
        self,
        *,
        fund_slug: str,
        instrument_id: str,
        session: AsyncSession | None = None,
    ) -> bool:
        """Remove an instrument from the restricted list. Returns True if deleted."""
        async with self._session(session) as session:
            stmt = delete(RestrictedInstrumentRecord).where(
                RestrictedInstrumentRecord.fund_slug == fund_slug,
                RestrictedInstrumentRecord.instrument_id == instrument_id,
            )
            result = await session.execute(stmt)
            return result.rowcount > 0
