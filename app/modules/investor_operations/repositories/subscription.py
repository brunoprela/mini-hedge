"""SubscriptionRequestRepository — CRUD for positions.subscription_requests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select, update

from app.modules.investor_operations.models.subscription import SubscriptionRequestRecord
from app.shared.repository import BaseRepository

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.ext.asyncio import AsyncSession


class SubscriptionRequestRepository(BaseRepository):
    """CRUD for positions.subscription_requests."""

    async def save(
        self, record: SubscriptionRequestRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as s:
            s.add(record)
            await s.flush()

    async def get_by_id(
        self, request_id: str, *, session: AsyncSession | None = None
    ) -> SubscriptionRequestRecord | None:
        async with self._session(session) as s:
            stmt = select(SubscriptionRequestRecord).where(
                SubscriptionRequestRecord.id == request_id
            )
            result = await s.execute(stmt)
            return result.scalar_one_or_none()

    async def list_by_state(
        self, state: str, *, session: AsyncSession | None = None
    ) -> list[SubscriptionRequestRecord]:
        async with self._session(session) as s:
            stmt = (
                select(SubscriptionRequestRecord)
                .where(SubscriptionRequestRecord.state == state)
                .order_by(SubscriptionRequestRecord.submitted_at)
            )
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def list_by_investor(
        self, investor_id: str, *, session: AsyncSession | None = None
    ) -> list[SubscriptionRequestRecord]:
        async with self._session(session) as s:
            stmt = (
                select(SubscriptionRequestRecord)
                .where(SubscriptionRequestRecord.investor_id == investor_id)
                .order_by(SubscriptionRequestRecord.submitted_at.desc())
            )
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def list_by_dealing_date(
        self, dealing_date: date, *, session: AsyncSession | None = None
    ) -> list[SubscriptionRequestRecord]:
        async with self._session(session) as s:
            stmt = (
                select(SubscriptionRequestRecord)
                .where(SubscriptionRequestRecord.dealing_date == dealing_date)
                .order_by(SubscriptionRequestRecord.submitted_at)
            )
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def update_state(
        self,
        request_id: str,
        new_state: str,
        *,
        session: AsyncSession | None = None,
        **extra_fields: object,
    ) -> None:
        async with self._session(session) as s:
            stmt = (
                update(SubscriptionRequestRecord)
                .where(SubscriptionRequestRecord.id == request_id)
                .values(state=new_state, **extra_fields)
            )
            await s.execute(stmt)

    async def count_by_state(self, *, session: AsyncSession | None = None) -> dict[str, int]:
        """Return {state: count} for all subscription requests."""
        from sqlalchemy import func

        async with self._session(session) as s:
            stmt = select(
                SubscriptionRequestRecord.state,
                func.count().label("cnt"),
            ).group_by(SubscriptionRequestRecord.state)
            result = await s.execute(stmt)
            return {row.state: row.cnt for row in result}
