"""Research note persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, select

from app.modules.ai_analysis.models.research_note import ResearchNoteRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ResearchNoteRepository(BaseRepository):
    """Repository for research notes."""

    async def save_note(
        self, record: ResearchNoteRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as s:
            s.add(record)
            await s.commit()

    async def list_notes(
        self,
        *,
        tags: list[str] | None = None,
        limit: int = 50,
        session: AsyncSession | None = None,
    ) -> list[ResearchNoteRecord]:
        async with self._session(session) as s:
            stmt = select(ResearchNoteRecord).order_by(ResearchNoteRecord.created_at.desc())
            if tags:
                # Filter notes that contain any of the requested tags
                for tag in tags:
                    stmt = stmt.where(ResearchNoteRecord.tags.op("@>")(f'["{tag}"]'))
            stmt = stmt.limit(limit)
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def get_note(
        self, note_id: str, *, session: AsyncSession | None = None
    ) -> ResearchNoteRecord | None:
        async with self._session(session) as s:
            result = await s.execute(
                select(ResearchNoteRecord).where(ResearchNoteRecord.id == note_id)
            )
            return result.scalar_one_or_none()

    async def delete_note(self, note_id: str, *, session: AsyncSession | None = None) -> None:
        async with self._session(session) as s:
            await s.execute(delete(ResearchNoteRecord).where(ResearchNoteRecord.id == note_id))
            await s.commit()
