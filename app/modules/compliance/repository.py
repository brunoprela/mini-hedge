"""Data access for compliance rules, violations, and trade decisions."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, update

from app.modules.compliance.models import (
    ComplianceRuleRecord,
    ComplianceViolationRecord,
    TradeDecisionRecord,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.shared.database import TenantSessionFactory


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


class _RepoBase:
    """Shared session-factory handling."""

    def __init__(
        self,
        session_factory: TenantSessionFactory,
        *,
        fund_slug: str | None = None,
    ) -> None:
        self._sf = session_factory
        self._fund_slug = fund_slug

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[AsyncSession]:
        if self._fund_slug is not None:
            async with self._sf.for_fund(self._fund_slug) as s:
                yield s
        else:
            async with self._sf() as s:
                yield s


# -------------------------------------------------------------------
# RuleRepository
# -------------------------------------------------------------------


class RuleRepository(_RepoBase):
    """CRUD for compliance rules."""

    async def get_all_by_fund(self, fund_slug: str) -> list[ComplianceRuleRecord]:
        async with self._session() as session:
            stmt = (
                select(ComplianceRuleRecord)
                .where(ComplianceRuleRecord.fund_slug == fund_slug)
                .order_by(ComplianceRuleRecord.created_at)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_active_by_fund(self, fund_slug: str) -> list[ComplianceRuleRecord]:
        async with self._session() as session:
            stmt = (
                select(ComplianceRuleRecord)
                .where(
                    ComplianceRuleRecord.fund_slug == fund_slug,
                    ComplianceRuleRecord.is_active.is_(True),
                )
                .order_by(ComplianceRuleRecord.created_at)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_by_id(self, rule_id: UUID) -> ComplianceRuleRecord | None:
        async with self._session() as session:
            stmt = select(ComplianceRuleRecord).where(ComplianceRuleRecord.id == str(rule_id))
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def insert(self, record: ComplianceRuleRecord) -> ComplianceRuleRecord:
        async with self._session() as session:
            session.add(record)
            await session.flush()
            await session.commit()
            await session.refresh(record)
            return record

    async def update(
        self,
        rule_id: UUID,
        **fields: object,
    ) -> ComplianceRuleRecord | None:
        async with self._session() as session:
            fields["updated_at"] = datetime.now(UTC)
            stmt = (
                update(ComplianceRuleRecord)
                .where(ComplianceRuleRecord.id == str(rule_id))
                .values(**fields)
            )
            await session.execute(stmt)
            await session.commit()
        return await self.get_by_id(rule_id)

    async def deactivate(self, rule_id: UUID) -> None:
        await self.update(rule_id, is_active=False, updated_at=datetime.now(UTC))


# -------------------------------------------------------------------
# ViolationRepository
# -------------------------------------------------------------------


class ViolationRepository(_RepoBase):
    """CRUD for compliance violations."""

    async def get_active_by_portfolio(self, portfolio_id: UUID) -> list[ComplianceViolationRecord]:
        async with self._session() as session:
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

    async def get_by_id(self, violation_id: UUID) -> ComplianceViolationRecord | None:
        async with self._session() as session:
            stmt = select(ComplianceViolationRecord).where(
                ComplianceViolationRecord.id == str(violation_id)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def insert(self, record: ComplianceViolationRecord) -> ComplianceViolationRecord:
        async with self._session() as session:
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
    ) -> ComplianceViolationRecord | None:
        now = datetime.now(UTC)
        async with self._session() as session:
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


class TradeDecisionRepository(_RepoBase):
    """Append-only log of trade compliance decisions."""

    async def insert(self, record: TradeDecisionRecord) -> TradeDecisionRecord:
        async with self._session() as session:
            session.add(record)
            await session.flush()
            await session.commit()
            await session.refresh(record)
            return record

    async def get_by_portfolio(self, portfolio_id: UUID) -> list[TradeDecisionRecord]:
        async with self._session() as session:
            stmt = (
                select(TradeDecisionRecord)
                .where(TradeDecisionRecord.portfolio_id == str(portfolio_id))
                .order_by(TradeDecisionRecord.decided_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
