"""Feature set persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.feature_store.models.feature_set import FeatureSetRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class FeatureSetRepository(BaseRepository):
    """CRUD for FeatureSetRecord."""

    async def insert(
        self, record: FeatureSetRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as s:
            s.add(record)
            await s.commit()

    async def get_by_id(
        self, set_id: str, *, session: AsyncSession | None = None
    ) -> FeatureSetRecord | None:
        async with self._session(session) as s:
            result = await s.execute(select(FeatureSetRecord).where(FeatureSetRecord.id == set_id))
            return result.scalar_one_or_none()

    async def list_all(self, *, session: AsyncSession | None = None) -> list[FeatureSetRecord]:
        async with self._session(session) as s:
            result = await s.execute(select(FeatureSetRecord).order_by(FeatureSetRecord.name))
            return list(result.scalars().all())
