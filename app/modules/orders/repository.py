"""Data access for orders and fills."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, update

from app.modules.orders.models import OrderFillRecord, OrderRecord

if TYPE_CHECKING:
    from app.shared.database import TenantSessionFactory


class OrderRepository:
    """CRUD for orders and fills."""

    def __init__(self, session_factory: TenantSessionFactory) -> None:
        self._sf = session_factory

    async def save(self, record: OrderRecord) -> OrderRecord:
        async with self._sf() as session:
            session.add(record)
            await session.flush()
            await session.commit()
            await session.refresh(record)
            return record

    async def get_by_id(self, order_id: UUID) -> OrderRecord | None:
        async with self._sf() as session:
            stmt = select(OrderRecord).where(OrderRecord.id == str(order_id))
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_portfolio(
        self,
        portfolio_id: UUID,
        state: str | None = None,
    ) -> list[OrderRecord]:
        async with self._sf() as session:
            stmt = select(OrderRecord).where(OrderRecord.portfolio_id == str(portfolio_id))
            if state is not None:
                stmt = stmt.where(OrderRecord.state == state)
            stmt = stmt.order_by(OrderRecord.created_at.desc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_open_orders(self, fund_slug: str) -> list[OrderRecord]:
        open_states = ["draft", "pending_compliance", "approved", "sent", "partially_filled"]
        async with self._sf() as session:
            stmt = (
                select(OrderRecord)
                .where(
                    OrderRecord.fund_slug == fund_slug,
                    OrderRecord.state.in_(open_states),
                )
                .order_by(OrderRecord.created_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def update_state(
        self,
        order_id: UUID,
        state: str,
        **fields: object,
    ) -> OrderRecord | None:
        async with self._sf() as session:
            values: dict[str, object] = {
                "state": state,
                "updated_at": datetime.now(UTC),
                **fields,
            }
            stmt = update(OrderRecord).where(OrderRecord.id == str(order_id)).values(**values)
            await session.execute(stmt)
            await session.commit()
        return await self.get_by_id(order_id)

    async def save_fill(self, fill: OrderFillRecord) -> OrderFillRecord:
        async with self._sf() as session:
            session.add(fill)
            await session.flush()
            await session.commit()
            await session.refresh(fill)
            return fill

    async def get_fills(self, order_id: UUID) -> list[OrderFillRecord]:
        async with self._sf() as session:
            stmt = (
                select(OrderFillRecord)
                .where(OrderFillRecord.order_id == str(order_id))
                .order_by(OrderFillRecord.filled_at)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
