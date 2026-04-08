"""Quant research data persistence."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.quant_research.models import (
    FactorDefinitionRecord,
    FactorExposureRecord,
    FactorReturnRecord,
    RegimeSnapshotRecord,
)
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class FactorRepository(BaseRepository):
    """Persistence for factor definitions, exposures, and returns."""

    async def create_factor(
        self, record: FactorDefinitionRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as s:
            s.add(record)
            await s.commit()

    async def get_factor(
        self, factor_id: str, *, session: AsyncSession | None = None
    ) -> FactorDefinitionRecord | None:
        async with self._session(session) as s:
            result = await s.execute(
                select(FactorDefinitionRecord).where(FactorDefinitionRecord.id == factor_id)
            )
            return result.scalar_one_or_none()

    async def get_by_name(
        self, name: str, *, session: AsyncSession | None = None
    ) -> FactorDefinitionRecord | None:
        async with self._session(session) as s:
            result = await s.execute(
                select(FactorDefinitionRecord).where(FactorDefinitionRecord.name == name)
            )
            return result.scalar_one_or_none()

    async def list_factors(
        self, *, active_only: bool = True, session: AsyncSession | None = None
    ) -> list[FactorDefinitionRecord]:
        async with self._session(session) as s:
            stmt = select(FactorDefinitionRecord)
            if active_only:
                stmt = stmt.where(FactorDefinitionRecord.is_active.is_(True))
            stmt = stmt.order_by(FactorDefinitionRecord.name)
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def save_exposures(
        self, records: list[FactorExposureRecord], *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as s:
            for r in records:
                s.add(r)
            await s.commit()

    async def get_exposures(
        self,
        factor_id: str,
        as_of_date: date,
        *,
        session: AsyncSession | None = None,
    ) -> list[FactorExposureRecord]:
        async with self._session(session) as s:
            result = await s.execute(
                select(FactorExposureRecord)
                .where(
                    FactorExposureRecord.factor_id == factor_id,
                    FactorExposureRecord.as_of_date == as_of_date,
                )
                .order_by(FactorExposureRecord.exposure.desc())
            )
            return list(result.scalars().all())

    async def save_returns(
        self, records: list[FactorReturnRecord], *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as s:
            for r in records:
                s.add(r)
            await s.commit()

    async def get_returns(
        self,
        factor_id: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        session: AsyncSession | None = None,
    ) -> list[FactorReturnRecord]:
        async with self._session(session) as s:
            stmt = select(FactorReturnRecord).where(FactorReturnRecord.factor_id == factor_id)
            if start_date is not None:
                stmt = stmt.where(FactorReturnRecord.return_date >= start_date)
            if end_date is not None:
                stmt = stmt.where(FactorReturnRecord.return_date <= end_date)
            stmt = stmt.order_by(FactorReturnRecord.return_date)
            result = await s.execute(stmt)
            return list(result.scalars().all())


class RegimeRepository(BaseRepository):
    """Persistence for regime detection snapshots."""

    async def save_snapshot(
        self, record: RegimeSnapshotRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as s:
            s.add(record)
            await s.commit()

    async def get_latest(
        self, *, session: AsyncSession | None = None
    ) -> RegimeSnapshotRecord | None:
        async with self._session(session) as s:
            result = await s.execute(
                select(RegimeSnapshotRecord)
                .order_by(RegimeSnapshotRecord.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def get_history(
        self, *, limit: int = 100, session: AsyncSession | None = None
    ) -> list[RegimeSnapshotRecord]:
        async with self._session(session) as s:
            result = await s.execute(
                select(RegimeSnapshotRecord)
                .order_by(RegimeSnapshotRecord.start_date.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
