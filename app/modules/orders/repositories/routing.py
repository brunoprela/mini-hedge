"""Data access for routing rules and routing decisions."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import delete, select

from app.modules.orders.models.routing_decision import RoutingDecisionRecord
from app.modules.orders.models.routing_rule import RoutingRuleRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession


class RoutingRepository(BaseRepository):
    """CRUD for routing rules and decisions (audit trail)."""

    # --- Routing rules ---

    async def get_rules_for_fund(
        self,
        fund_slug: str,
        instrument_class: str | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> list[RoutingRuleRecord]:
        async with self._session(session) as session:
            stmt = (
                select(RoutingRuleRecord)
                .where(
                    RoutingRuleRecord.fund_slug == fund_slug,
                    RoutingRuleRecord.is_active.is_(True),
                )
                .order_by(RoutingRuleRecord.priority.desc())
            )
            if instrument_class is not None:
                stmt = stmt.where(
                    (RoutingRuleRecord.instrument_class == instrument_class)
                    | RoutingRuleRecord.instrument_class.is_(None),
                )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def save_rule(
        self,
        record: RoutingRuleRecord,
        *,
        session: AsyncSession | None = None,
    ) -> RoutingRuleRecord:
        async with self._session(session) as session:
            session.add(record)
            await session.flush()
            await session.commit()
            await session.refresh(record)
            return record

    async def delete_rule(
        self,
        rule_id: UUID,
        *,
        fund_slug: str | None = None,
        session: AsyncSession | None = None,
    ) -> bool:
        async with self._session(session) as session:
            stmt = delete(RoutingRuleRecord).where(
                RoutingRuleRecord.id == str(rule_id),
            )
            if fund_slug is not None:
                stmt = stmt.where(RoutingRuleRecord.fund_slug == fund_slug)
            result = await session.execute(stmt)
            await session.commit()
            return bool(getattr(result, "rowcount", 0) > 0)

    # --- Routing decisions (audit trail) ---

    async def save_decision(
        self,
        record: RoutingDecisionRecord,
        *,
        session: AsyncSession | None = None,
    ) -> RoutingDecisionRecord:
        async with self._session(session) as session:
            session.add(record)
            await session.flush()
            await session.commit()
            await session.refresh(record)
            return record

    async def get_decisions_for_order(
        self,
        order_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> list[RoutingDecisionRecord]:
        async with self._session(session) as session:
            stmt = (
                select(RoutingDecisionRecord)
                .where(RoutingDecisionRecord.order_id == str(order_id))
                .order_by(RoutingDecisionRecord.decided_at)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_decisions_in_range(
        self,
        start: datetime,
        end: datetime,
        *,
        session: AsyncSession | None = None,
    ) -> list[RoutingDecisionRecord]:
        async with self._session(session) as session:
            stmt = (
                select(RoutingDecisionRecord)
                .where(
                    RoutingDecisionRecord.decided_at >= start,
                    RoutingDecisionRecord.decided_at <= end,
                )
                .order_by(RoutingDecisionRecord.decided_at)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
