"""Data access for swap extensions."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.security_master.models.swap_extension import SwapExtensionRecord
from app.shared.repository import BaseRepository


class SwapExtensionRepository(BaseRepository):
    async def insert_batch_extensions(
        self, records: list[SwapExtensionRecord], *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            for record in records:
                await session.merge(record)
            await session.commit()
