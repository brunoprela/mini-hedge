"""AI analysis result persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.ai_analysis.models.analysis_result import AnalysisResultRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class AnalysisResultRepository(BaseRepository):
    """Repository for AI analysis results."""

    async def save_result(
        self, record: AnalysisResultRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as s:
            s.add(record)
            await s.commit()

    async def get_result(
        self, result_id: str, *, session: AsyncSession | None = None
    ) -> AnalysisResultRecord | None:
        async with self._session(session) as s:
            result = await s.execute(
                select(AnalysisResultRecord).where(AnalysisResultRecord.id == result_id)
            )
            return result.scalar_one_or_none()

    async def list_results(
        self,
        *,
        analysis_type: str | None = None,
        limit: int = 50,
        session: AsyncSession | None = None,
    ) -> list[AnalysisResultRecord]:
        async with self._session(session) as s:
            stmt = select(AnalysisResultRecord).order_by(AnalysisResultRecord.created_at.desc())
            if analysis_type is not None:
                stmt = stmt.where(AnalysisResultRecord.analysis_type == analysis_type)
            stmt = stmt.limit(limit)
            result = await s.execute(stmt)
            return list(result.scalars().all())
