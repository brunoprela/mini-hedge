"""VaR contribution persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.risk_engine.models.var_contribution import VaRContributionRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class VaRContributionRepository(BaseRepository):
    async def insert_contributions(
        self,
        contributions: list[VaRContributionRecord],
        *,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as session:
            for c in contributions:
                session.add(c)
            await session.commit()

    async def get_var_contributions(
        self, var_result_id: str, *, session: AsyncSession | None = None
    ) -> list[VaRContributionRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(VaRContributionRecord).where(
                    VaRContributionRecord.var_result_id == var_result_id
                )
            )
            return list(result.scalars().all())
