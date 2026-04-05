"""Data access for fund records."""

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.models import FundRecord, FundStatus
from app.shared.repository import BaseRepository


class FundRepository(BaseRepository):
    async def get_by_id(
        self, fund_id: str, *, session: AsyncSession | None = None
    ) -> FundRecord | None:
        async with self._session(session) as session:
            result = await session.execute(select(FundRecord).where(FundRecord.id == fund_id))
            return result.scalar_one_or_none()

    async def get_by_slug(
        self, slug: str, *, session: AsyncSession | None = None
    ) -> FundRecord | None:
        async with self._session(session) as session:
            result = await session.execute(select(FundRecord).where(FundRecord.slug == slug))
            return result.scalar_one_or_none()

    async def get_all_active(self, *, session: AsyncSession | None = None) -> list[FundRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(FundRecord).where(FundRecord.status == FundStatus.ACTIVE)
            )
            return list(result.scalars().all())

    async def get_all(self, *, session: AsyncSession | None = None) -> list[FundRecord]:
        async with self._session(session) as session:
            result = await session.execute(select(FundRecord))
            return list(result.scalars().all())

    async def get_all_paginated(
        self, *, limit: int = 100, offset: int = 0, session: AsyncSession | None = None
    ) -> tuple[list[FundRecord], int]:
        async with self._session(session) as session:
            total = (await session.execute(select(func.count(FundRecord.id)))).scalar_one()
            result = await session.execute(
                select(FundRecord).order_by(FundRecord.name).offset(offset).limit(limit)
            )
            return list(result.scalars().all()), total

    async def insert(self, record: FundRecord, *, session: AsyncSession | None = None) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def update(
        self, fund_id: str, *, session: AsyncSession | None = None, **fields: object
    ) -> FundRecord | None:
        async with self._session(session) as session:
            if fields:
                await session.execute(
                    update(FundRecord).where(FundRecord.id == fund_id).values(**fields)
                )
                await session.commit()
            result = await session.execute(select(FundRecord).where(FundRecord.id == fund_id))
            return result.scalar_one_or_none()
