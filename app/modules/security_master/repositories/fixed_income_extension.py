"""Data access for fixed income extensions."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.security_master.models.fixed_income_extension import FixedIncomeExtensionRecord
from app.shared.repository import BaseRepository


class FixedIncomeExtensionRepository(BaseRepository):
    async def insert_batch_extensions(
        self, records: list[FixedIncomeExtensionRecord], *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            for record in records:
                await session.merge(record)
            await session.commit()
