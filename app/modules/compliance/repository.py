"""Data access for compliance rules, violations, and trade decisions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, update

from app.modules.compliance.interface import UpdateRuleRequest
from app.modules.compliance.models import (
    ComplianceRuleRecord,
    ComplianceViolationRecord,
    TradeDecisionRecord,
)
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# -------------------------------------------------------------------
# RuleRepository
# -------------------------------------------------------------------


class RuleRepository(BaseRepository):
    """CRUD for compliance rules."""

    async def get_all(self, *, session: AsyncSession | None = None) -> list[ComplianceRuleRecord]:
        async with self._session(session) as session:
            stmt = select(ComplianceRuleRecord).order_by(ComplianceRuleRecord.created_at)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_active(
        self, *, session: AsyncSession | None = None
    ) -> list[ComplianceRuleRecord]:
        async with self._session(session) as session:
            stmt = (
                select(ComplianceRuleRecord)
                .where(ComplianceRuleRecord.is_active.is_(True))
                .order_by(ComplianceRuleRecord.created_at)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_by_id(
        self, rule_id: UUID, *, session: AsyncSession | None = None
    ) -> ComplianceRuleRecord | None:
        async with self._session(session) as session:
            stmt = select(ComplianceRuleRecord).where(ComplianceRuleRecord.id == str(rule_id))
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def insert(
        self, record: ComplianceRuleRecord, *, session: AsyncSession | None = None
    ) -> ComplianceRuleRecord:
        async with self._session(session) as session:
            session.add(record)
            await session.flush()
            await session.commit()
            await session.refresh(record)
            return record

    async def update(
        self,
        rule_id: UUID,
        updates: UpdateRuleRequest,
        *,
        session: AsyncSession | None = None,
    ) -> ComplianceRuleRecord | None:
        async with self._session(session) as session:
            values = updates.model_dump(exclude_none=True)
            # Normalise enum values to their string representations
            if "rule_type" in values:
                values["rule_type"] = str(values["rule_type"])
            if "severity" in values:
                values["severity"] = str(values["severity"])
            values["updated_at"] = datetime.now(UTC)
            stmt = (
                update(ComplianceRuleRecord)
                .where(ComplianceRuleRecord.id == str(rule_id))
                .values(**values)
            )
            await session.execute(stmt)
            await session.commit()
        return await self.get_by_id(rule_id)

    async def deactivate(self, rule_id: UUID, *, session: AsyncSession | None = None) -> None:
        await self.update(rule_id, UpdateRuleRequest(is_active=False), session=session)


# -------------------------------------------------------------------
# ViolationRepository
# -------------------------------------------------------------------


class ViolationRepository(BaseRepository):
    """CRUD for compliance violations."""

    async def get_active_by_portfolio(
        self, portfolio_id: UUID, *, session: AsyncSession | None = None
    ) -> list[ComplianceViolationRecord]:
        async with self._session(session) as session:
            stmt = (
                select(ComplianceViolationRecord)
                .where(
                    ComplianceViolationRecord.portfolio_id == str(portfolio_id),
                    ComplianceViolationRecord.resolved_at.is_(None),
                )
                .order_by(ComplianceViolationRecord.detected_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_by_id(
        self, violation_id: UUID, *, session: AsyncSession | None = None
    ) -> ComplianceViolationRecord | None:
        async with self._session(session) as session:
            stmt = select(ComplianceViolationRecord).where(
                ComplianceViolationRecord.id == str(violation_id)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def insert(
        self, record: ComplianceViolationRecord, *, session: AsyncSession | None = None
    ) -> ComplianceViolationRecord:
        async with self._session(session) as session:
            session.add(record)
            await session.flush()
            await session.commit()
            await session.refresh(record)
            return record

    async def resolve(
        self,
        violation_id: UUID,
        resolved_by: str,
        resolution_type: str = "manual",
        *,
        session: AsyncSession | None = None,
    ) -> ComplianceViolationRecord | None:
        now = datetime.now(UTC)
        async with self._session(session) as session:
            stmt = (
                update(ComplianceViolationRecord)
                .where(ComplianceViolationRecord.id == str(violation_id))
                .values(
                    resolved_at=now,
                    resolved_by=resolved_by,
                    resolution_type=resolution_type,
                )
            )
            await session.execute(stmt)
            await session.commit()
        return await self.get_by_id(violation_id)


# -------------------------------------------------------------------
# TradeDecisionRepository
# -------------------------------------------------------------------


class TradeDecisionRepository(BaseRepository):
    """Append-only log of trade compliance decisions."""

    async def insert(
        self, record: TradeDecisionRecord, *, session: AsyncSession | None = None
    ) -> TradeDecisionRecord:
        async with self._session(session) as session:
            session.add(record)
            await session.flush()
            await session.commit()
            await session.refresh(record)
            return record

    async def get_by_portfolio(
        self, portfolio_id: UUID, *, session: AsyncSession | None = None
    ) -> list[TradeDecisionRecord]:
        async with self._session(session) as session:
            stmt = (
                select(TradeDecisionRecord)
                .where(TradeDecisionRecord.portfolio_id == str(portfolio_id))
                .order_by(TradeDecisionRecord.decided_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
