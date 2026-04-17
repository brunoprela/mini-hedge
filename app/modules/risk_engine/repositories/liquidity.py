"""Liquidity profile persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.risk_engine.models.liquidity_profile import LiquidityProfileRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class LiquidityRepository(BaseRepository):
    async def insert_liquidity_profile(
        self, record: LiquidityProfileRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def get_latest_liquidity(
        self, portfolio_id: UUID, *, session: AsyncSession | None = None
    ) -> LiquidityProfileRecord | None:
        async with self._session(session) as session:
            result = await session.execute(
                select(LiquidityProfileRecord)
                .where(LiquidityProfileRecord.portfolio_id == str(portfolio_id))
                .order_by(LiquidityProfileRecord.business_date.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
