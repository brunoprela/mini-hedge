"""Data access for future extensions."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.security_master.models.future_extension import FutureExtensionRecord
from app.shared.repository import BaseRepository


class FutureExtensionRepository(BaseRepository):
    async def insert_batch_extensions(
        self, records: list[FutureExtensionRecord], *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            for record in records:
                await session.merge(record)
            await session.commit()
