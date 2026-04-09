"""Data access for equity extensions."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.security_master.models.equity_extension import EquityExtensionRecord
from app.shared.repository import BaseRepository


class EquityExtensionRepository(BaseRepository):
    async def insert_batch_extensions(
        self, records: list[EquityExtensionRecord], *, session: AsyncSession | None = None
    ) -> None:
        """Insert extensions only."""
        async with self._session(session) as session:
            for record in records:
                await session.merge(record)
            await session.commit()
