"""Data access for FX extensions."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.security_master.models.fx_extension import FXExtensionRecord
from app.shared.repository import BaseRepository


class FXExtensionRepository(BaseRepository):
    async def insert_batch_extensions(
        self, records: list[FXExtensionRecord], *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            for record in records:
                await session.merge(record)
            await session.commit()
