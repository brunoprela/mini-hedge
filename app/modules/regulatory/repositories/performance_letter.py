"""Performance letter persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.regulatory.models.performance_letter import PerformanceLetterRecord


class PerformanceLetterRepository(BaseRepository):
    """CRUD for PerformanceLetterRecord."""

    async def save(
        self, record: PerformanceLetterRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def list_all(
        self,
        *,
        session: AsyncSession | None = None,
    ) -> list[PerformanceLetterRecord]:
        from sqlalchemy import select

        from app.modules.regulatory.models.performance_letter import PerformanceLetterRecord

        async with self._session(session) as session:
            stmt = (
                select(PerformanceLetterRecord)
                .order_by(PerformanceLetterRecord.period.desc())
                .limit(50)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
