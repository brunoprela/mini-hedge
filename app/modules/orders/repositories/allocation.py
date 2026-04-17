"""Data access for block allocations and legs — platform schema."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, update

from app.modules.orders.models import (
    AllocationLegRecord,
    BlockAllocationRecord,
)
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class AllocationRepository(BaseRepository):
    """CRUD for block allocations and allocation legs (platform schema)."""

    async def insert_allocation(
        self, record: BlockAllocationRecord, *, session: AsyncSession | None = None
    ) -> BlockAllocationRecord:
        async with self._session(session) as session:
            session.add(record)
            await session.flush()
            await session.commit()
            await session.refresh(record)
            return record

    async def insert_leg(
        self, leg: AllocationLegRecord, *, session: AsyncSession | None = None
    ) -> AllocationLegRecord:
        async with self._session(session) as session:
            session.add(leg)
            await session.flush()
            await session.commit()
            await session.refresh(leg)
            return leg

    async def get_allocation_by_id(
        self, allocation_id: UUID, *, session: AsyncSession | None = None
    ) -> BlockAllocationRecord | None:
        async with self._session(session) as session:
            stmt = select(BlockAllocationRecord).where(
                BlockAllocationRecord.id == str(allocation_id)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_legs(
        self, allocation_id: UUID, *, session: AsyncSession | None = None
    ) -> list[AllocationLegRecord]:
        async with self._session(session) as session:
            stmt = (
                select(AllocationLegRecord)
                .where(AllocationLegRecord.block_allocation_id == str(allocation_id))
                .order_by(AllocationLegRecord.created_at)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def update_allocation_state(
        self,
        allocation_id: UUID,
        state: str,
        *,
        filled_quantity: Decimal | None = None,
        avg_fill_price: Decimal | None = None,
        execution_fund_slug: str | None = None,
        execution_order_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> BlockAllocationRecord | None:
        async with self._session(session) as session:
            values: dict[str, object] = {
                "state": state,
                "updated_at": datetime.now(UTC),
            }
            if filled_quantity is not None:
                values["filled_quantity"] = filled_quantity
            if avg_fill_price is not None:
                values["avg_fill_price"] = avg_fill_price
            if execution_fund_slug is not None:
                values["execution_fund_slug"] = execution_fund_slug
            if execution_order_id is not None:
                values["execution_order_id"] = execution_order_id
            stmt = (
                update(BlockAllocationRecord)
                .where(BlockAllocationRecord.id == str(allocation_id))
                .values(**values)
            )
            await session.execute(stmt)
            await session.commit()
        return await self.get_allocation_by_id(allocation_id)

    async def update_leg(
        self,
        leg_id: UUID,
        *,
        filled_quantity: Decimal | None = None,
        avg_fill_price: Decimal | None = None,
        allocated_order_id: str | None = None,
        state: str | None = None,
        compliance_results: dict[str, object] | list[dict[str, object]] | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        async with self._session(session) as session:
            values: dict[str, object] = {}
            if filled_quantity is not None:
                values["filled_quantity"] = filled_quantity
            if avg_fill_price is not None:
                values["avg_fill_price"] = avg_fill_price
            if allocated_order_id is not None:
                values["allocated_order_id"] = allocated_order_id
            if state is not None:
                values["state"] = state
            if compliance_results is not None:
                values["compliance_results"] = compliance_results
            if values:
                stmt = (
                    update(AllocationLegRecord)
                    .where(AllocationLegRecord.id == str(leg_id))
                    .values(**values)
                )
                await session.execute(stmt)
                await session.commit()
