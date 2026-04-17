"""Margin requirement persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.risk_engine.models.margin_requirement import MarginRequirementRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class MarginRepository(BaseRepository):
    async def insert_margin_requirement(
        self, record: MarginRequirementRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()

    async def get_latest_margin(
        self, portfolio_id: UUID, *, session: AsyncSession | None = None
    ) -> MarginRequirementRecord | None:
        async with self._session(session) as session:
            result = await session.execute(
                select(MarginRequirementRecord)
                .where(MarginRequirementRecord.portfolio_id == str(portfolio_id))
                .order_by(MarginRequirementRecord.business_date.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
