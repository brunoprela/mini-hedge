"""Order intent persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, update

from app.modules.alpha_engine.models.order_intent import OrderIntentRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class OrderIntentRepository(BaseRepository):
    """CRUD for OrderIntentRecord."""

    async def insert_batch(
        self, records: list[OrderIntentRecord], *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            for i in records:
                session.add(i)
            await session.commit()

    async def get_by_portfolio(
        self, portfolio_id: UUID, *, session: AsyncSession | None = None
    ) -> list[OrderIntentRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(OrderIntentRecord)
                .where(
                    OrderIntentRecord.portfolio_id == str(portfolio_id),
                    OrderIntentRecord.status == "draft",
                )
                .order_by(OrderIntentRecord.created_at.desc())
            )
            return list(result.scalars().all())

    async def get_by_run(
        self, run_id: str, *, session: AsyncSession | None = None
    ) -> list[OrderIntentRecord]:
        async with self._session(session) as session:
            result = await session.execute(
                select(OrderIntentRecord).where(OrderIntentRecord.optimization_run_id == run_id)
            )
            return list(result.scalars().all())

    async def update_status(
        self, intent_id: str, status: str, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as session:
            await session.execute(
                update(OrderIntentRecord)
                .where(OrderIntentRecord.id == intent_id)
                .values(status=status)
            )
            await session.commit()
