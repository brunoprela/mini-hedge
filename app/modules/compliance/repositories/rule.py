"""Compliance rule repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, update

from app.modules.compliance.interfaces import UpdateRuleRequest
from app.modules.compliance.models.compliance_rule import ComplianceRuleRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class RuleRepository(BaseRepository):
    """CRUD for compliance rules."""

    async def list_all(self, *, session: AsyncSession | None = None) -> list[ComplianceRuleRecord]:
        async with self._session(session) as session:
            stmt = select(ComplianceRuleRecord).order_by(ComplianceRuleRecord.created_at)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def list_active(
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
