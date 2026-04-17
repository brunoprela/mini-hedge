"""Counterparty persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.risk_engine.models.counterparty import CounterpartyRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CounterpartyRepository(BaseRepository):
    async def list_counterparties(
        self, *, session: AsyncSession | None = None
    ) -> list[CounterpartyRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(CounterpartyRecord)
                .where(CounterpartyRecord.is_active.is_(True))
                .order_by(CounterpartyRecord.name)
            )
            return list(result.scalars().all())

    async def get_counterparty(
        self, counterparty_id: str, *, session: AsyncSession | None = None
    ) -> CounterpartyRecord | None:
        async with self._session(session) as session:
            result = await session.execute(
                select(CounterpartyRecord).where(CounterpartyRecord.id == counterparty_id)
            )
            return result.scalar_one_or_none()

    async def get_counterparty_map(self, *, session: AsyncSession | None = None) -> dict[str, str]:
        records = await self.list_counterparties(session=session)
        return {r.id: r.name for r in records}

    async def insert_counterparty(
        self, record: CounterpartyRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            session.add(record)
            await session.commit()
