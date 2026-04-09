"""Alternative data feed persistence layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select, update

from app.modules.alt_data.models.alt_data_feed import AltDataFeedRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession


class AltDataFeedRepository(BaseRepository):
    """CRUD operations for alternative data feeds."""

    async def create_feed(
        self, record: AltDataFeedRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as s:
            s.add(record)
            await s.commit()

    async def get_feed(
        self, feed_id: str, *, session: AsyncSession | None = None
    ) -> AltDataFeedRecord | None:
        async with self._session(session) as s:
            result = await s.execute(
                select(AltDataFeedRecord).where(AltDataFeedRecord.id == feed_id)
            )
            return result.scalar_one_or_none()

    async def get_feed_by_name(
        self, name: str, *, session: AsyncSession | None = None
    ) -> AltDataFeedRecord | None:
        async with self._session(session) as s:
            result = await s.execute(
                select(AltDataFeedRecord).where(AltDataFeedRecord.name == name)
            )
            return result.scalar_one_or_none()

    async def list_feeds(
        self,
        *,
        source: str | None = None,
        active_only: bool = True,
        session: AsyncSession | None = None,
    ) -> list[AltDataFeedRecord]:
        async with self._session(session) as s:
            stmt = select(AltDataFeedRecord)
            if source is not None:
                stmt = stmt.where(AltDataFeedRecord.source == source)
            if active_only:
                stmt = stmt.where(AltDataFeedRecord.is_active.is_(True))
            stmt = stmt.order_by(AltDataFeedRecord.name)
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def update_feed(
        self,
        feed_id: str,
        *,
        last_updated: datetime | None = None,
        record_count: int | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as s:
            values: dict[str, object] = {}
            if last_updated is not None:
                values["last_updated"] = last_updated
            if record_count is not None:
                values["record_count"] = record_count
            if values:
                await s.execute(
                    update(AltDataFeedRecord)
                    .where(AltDataFeedRecord.id == feed_id)
                    .values(**values)
                )
                await s.commit()
