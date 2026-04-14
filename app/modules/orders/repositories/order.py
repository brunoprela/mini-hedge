"""Data access for orders."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, update

from app.modules.orders.models.order import OrderRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class OrderRepository(BaseRepository):
    """CRUD for orders."""

    async def save(
        self, record: OrderRecord, *, session: AsyncSession | None = None
    ) -> OrderRecord:
        async with self._session(session) as session:
            session.add(record)
            await session.flush()
            await session.commit()
            await session.refresh(record)
            return record

    async def get_by_id(
        self, order_id: UUID, *, session: AsyncSession | None = None
    ) -> OrderRecord | None:
        async with self._session(session) as session:
            stmt = select(OrderRecord).where(OrderRecord.id == str(order_id))
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_by_portfolio(
        self,
        portfolio_id: UUID,
        state: str | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> list[OrderRecord]:
        async with self._session(session) as session:
            stmt = select(OrderRecord).where(OrderRecord.portfolio_id == str(portfolio_id))
            if state is not None:
                stmt = stmt.where(OrderRecord.state == state)
            stmt = stmt.order_by(OrderRecord.created_at.desc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_open_orders(
        self, fund_slug: str, *, session: AsyncSession | None = None
    ) -> list[OrderRecord]:
        open_states = [
            "draft",
            "pending_compliance",
            "approved",
            "sent",
            "working",
            "partially_filled",
        ]
        async with self._session(session) as session:
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
        *,
        rejection_reason: str | None = None,
        compliance_results: dict[str, object] | list[dict[str, object]] | None = None,
        filled_quantity: Decimal | None = None,
        avg_fill_price: Decimal | None = None,
        broker_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> OrderRecord:
        async with self._session(session) as session:
            values: dict[str, object] = {
                "state": state,
                "updated_at": datetime.now(UTC),
            }
            if rejection_reason is not None:
                values["rejection_reason"] = rejection_reason
            if compliance_results is not None:
                values["compliance_results"] = compliance_results
            if filled_quantity is not None:
                values["filled_quantity"] = filled_quantity
            if avg_fill_price is not None:
                values["avg_fill_price"] = avg_fill_price
            if broker_id is not None:
                values["broker_id"] = broker_id
            stmt = update(OrderRecord).where(OrderRecord.id == str(order_id)).values(**values)
            await session.execute(stmt)
            await session.commit()
        result = await self.get_by_id(order_id)
        assert result is not None, f"Order {order_id} not found after update"
        return result

    async def get_children(
        self,
        parent_order_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> list[OrderRecord]:
        async with self._session(session) as session:
            stmt = (
                select(OrderRecord)
                .where(OrderRecord.parent_order_id == str(parent_order_id))
                .order_by(OrderRecord.created_at)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_active_children(
        self,
        parent_order_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> list[OrderRecord]:
        active_states = ["draft", "pending_compliance", "approved", "sent", "working", "partially_filled"]
        async with self._session(session) as session:
            stmt = (
                select(OrderRecord)
                .where(
                    OrderRecord.parent_order_id == str(parent_order_id),
                    OrderRecord.state.in_(active_states),
                )
                .order_by(OrderRecord.created_at)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_working_parents(
        self,
        *,
        session: AsyncSession | None = None,
    ) -> list[OrderRecord]:
        """Find all parent orders in WORKING state (for crash recovery)."""
        async with self._session(session) as session:
            stmt = select(OrderRecord).where(
                OrderRecord.is_parent.is_(True),
                OrderRecord.state == "working",
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
