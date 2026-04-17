"""Risk factor contribution persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.attribution.models.risk_factor_contribution import RiskFactorContributionRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class RiskFactorContributionRepository(BaseRepository):
    """CRUD for RiskFactorContributionRecord."""

    async def insert_batch(
        self,
        records: list[RiskFactorContributionRecord],
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as session:
            for r in records:
                session.add(r)
            await session.commit()

    async def get_by_rb_result(
        self, rb_result_id: str, *, session: AsyncSession | None = None
    ) -> list[RiskFactorContributionRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(RiskFactorContributionRecord).where(
                    RiskFactorContributionRecord.rb_result_id == rb_result_id
                )
            )
            return list(result.scalars().all())
