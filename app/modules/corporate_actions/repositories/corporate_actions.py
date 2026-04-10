"""Data access for processed corporate actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.modules.corporate_actions.models import ProcessedCorporateActionRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CorporateActionsRepository(BaseRepository):
    """CRUD for processed corporate actions."""

    async def get_by_action_id(
        self, action_id: str, *, session: AsyncSession | None = None
    ) -> ProcessedCorporateActionRecord | None:
        """Look up a processed action by its external action_id (idempotency check)."""
        async with self._session(session) as session:
            stmt = select(ProcessedCorporateActionRecord).where(
                ProcessedCorporateActionRecord.action_id == action_id
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def save(
        self,
        record: ProcessedCorporateActionRecord,
        *,
        session: AsyncSession | None = None,
    ) -> ProcessedCorporateActionRecord:
        """Insert a new processed corporate action record."""
        async with self._session(session) as session:
            session.add(record)
            await session.flush()
            await session.commit()
            await session.refresh(record)
            return record

    async def get_pending(
        self,
        instrument_id: str | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> list[ProcessedCorporateActionRecord]:
        """List all records with status=PENDING, optionally filtered by instrument."""
        async with self._session(session) as session:
            stmt = select(ProcessedCorporateActionRecord).where(
                ProcessedCorporateActionRecord.status == "pending"
            )
            if instrument_id is not None:
                stmt = stmt.where(ProcessedCorporateActionRecord.instrument_id == instrument_id)
            stmt = stmt.order_by(ProcessedCorporateActionRecord.created_at.desc())
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def list_all(
        self, *, session: AsyncSession | None = None
    ) -> list[ProcessedCorporateActionRecord]:
        """List all processed corporate action records."""
        async with self._session(session) as session:
            stmt = select(ProcessedCorporateActionRecord).order_by(
                ProcessedCorporateActionRecord.created_at.desc()
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
