"""Data access for option extensions."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.security_master.models.option_extension import OptionExtensionRecord
from app.shared.repository import BaseRepository


class OptionExtensionRepository(BaseRepository):
    async def insert_batch_extensions(
        self, records: list[OptionExtensionRecord], *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            for record in records:
                await session.merge(record)
            await session.commit()
