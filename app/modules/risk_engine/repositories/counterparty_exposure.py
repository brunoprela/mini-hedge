"""Counterparty exposure persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.modules.risk_engine.models.counterparty_exposure import CounterpartyExposureRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CounterpartyExposureRepository(BaseRepository):
    async def get_counterparty_exposures(
        self, portfolio_id: UUID, *, session: AsyncSession | None = None
    ) -> list[CounterpartyExposureRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(CounterpartyExposureRecord)
                .where(CounterpartyExposureRecord.portfolio_id == str(portfolio_id))
                .order_by(CounterpartyExposureRecord.business_date.desc())
                .limit(50)
            )
            return list(result.scalars().all())

    async def insert_counterparty_exposure(
        self, record: CounterpartyExposureRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()
