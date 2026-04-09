"""Investor repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.platform.models.investor import InvestorRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class InvestorRepository(BaseRepository):
    """CRUD for platform.investors."""

    async def get_all_active(self, *, session: AsyncSession | None = None) -> list[InvestorRecord]:
        async with self._session(session) as session:
            stmt = (
                select(InvestorRecord)
                .where(InvestorRecord.is_active.is_(True))
                .order_by(InvestorRecord.name)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_by_id(
        self, investor_id: str, *, session: AsyncSession | None = None
    ) -> InvestorRecord | None:
        async with self._session(session) as session:
            stmt = select(InvestorRecord).where(InvestorRecord.id == investor_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def insert(self, record: InvestorRecord, *, session: AsyncSession | None = None) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.flush()
            await session.commit()

    async def insert_batch(
        self, records: list[InvestorRecord], *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add_all(records)
            await session.flush()
            await session.commit()
