"""Data access for fund records."""

from sqlalchemy import select, update

from app.modules.platform.models import FundRecord, FundStatus
from app.shared.database import TenantSessionFactory


class FundRepository:
    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._session_factory = session_factory

    async def get_by_id(self, fund_id: str) -> FundRecord | None:
        async with self._session_factory() as session:
            result = await session.execute(select(FundRecord).where(FundRecord.id == fund_id))
            return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> FundRecord | None:
        async with self._session_factory() as session:
            result = await session.execute(select(FundRecord).where(FundRecord.slug == slug))
            return result.scalar_one_or_none()

    async def get_all_active(self) -> list[FundRecord]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(FundRecord).where(FundRecord.status == FundStatus.ACTIVE)
            )
            return list(result.scalars().all())

    async def get_all(self) -> list[FundRecord]:
        async with self._session_factory() as session:
            result = await session.execute(select(FundRecord))
            return list(result.scalars().all())

    async def insert(self, record: FundRecord) -> None:
        async with self._session_factory() as session:
            session.add(record)
            await session.commit()

    async def update(self, fund_id: str, **fields: object) -> FundRecord | None:
        async with self._session_factory() as session:
            if fields:
                await session.execute(
                    update(FundRecord).where(FundRecord.id == fund_id).values(**fields)
                )
                await session.commit()
            result = await session.execute(select(FundRecord).where(FundRecord.id == fund_id))
            return result.scalar_one_or_none()
