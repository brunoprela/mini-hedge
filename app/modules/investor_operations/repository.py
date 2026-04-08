"""Data access for investor operations — subscriptions, redemptions, fund terms, KYC."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select, update

from app.modules.investor_operations.models import (
    FundTermsRecord,
    InvestorKYCRecord,
    RedemptionRequestRecord,
    SubscriptionRequestRecord,
)
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

    async def count_by_state(
        self, *, session: AsyncSession | None = None
    ) -> dict[str, int]:
        """Return {state: count} for all subscription requests."""
        from sqlalchemy import func

        async with self._session(session) as s:
            stmt = select(
                SubscriptionRequestRecord.state,
                func.count().label("cnt"),
            ).group_by(SubscriptionRequestRecord.state)
            result = await s.execute(stmt)
            return {row.state: row.cnt for row in result}


class RedemptionRequestRepository(BaseRepository):
    """CRUD for positions.redemption_requests."""

    async def save(
        self, record: RedemptionRequestRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as s:
            s.add(record)
            await s.flush()

    async def get_by_id(
        self, request_id: str, *, session: AsyncSession | None = None
    ) -> RedemptionRequestRecord | None:
        async with self._session(session) as s:
            stmt = select(RedemptionRequestRecord).where(
                RedemptionRequestRecord.id == request_id
            )
            result = await s.execute(stmt)
            return result.scalar_one_or_none()

    async def list_by_state(
        self, state: str, *, session: AsyncSession | None = None
    ) -> list[RedemptionRequestRecord]:
        async with self._session(session) as s:
            stmt = (
                select(RedemptionRequestRecord)
                .where(RedemptionRequestRecord.state == state)
                .order_by(RedemptionRequestRecord.submitted_at)
            )
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def list_by_investor(
        self, investor_id: str, *, session: AsyncSession | None = None
    ) -> list[RedemptionRequestRecord]:
        async with self._session(session) as s:
            stmt = (
                select(RedemptionRequestRecord)
                .where(RedemptionRequestRecord.investor_id == investor_id)
                .order_by(RedemptionRequestRecord.submitted_at.desc())
            )
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def list_by_dealing_date(
        self, dealing_date: date, *, session: AsyncSession | None = None
    ) -> list[RedemptionRequestRecord]:
        async with self._session(session) as s:
            stmt = (
                select(RedemptionRequestRecord)
                .where(RedemptionRequestRecord.dealing_date == dealing_date)
                .order_by(RedemptionRequestRecord.submitted_at)
            )
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def list_pending_for_gate(
        self, *, session: AsyncSession | None = None
    ) -> list[RedemptionRequestRecord]:
        """Return validated/pending_gate_check redemptions awaiting gate processing."""
        async with self._session(session) as s:
            stmt = (
                select(RedemptionRequestRecord)
                .where(
                    RedemptionRequestRecord.state.in_(
                        ["validated", "pending_gate_check"]
                    )
                )
                .order_by(RedemptionRequestRecord.submitted_at)
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
                update(RedemptionRequestRecord)
                .where(RedemptionRequestRecord.id == request_id)
                .values(state=new_state, **extra_fields)
            )
            await s.execute(stmt)

    async def count_by_state(
        self, *, session: AsyncSession | None = None
    ) -> dict[str, int]:
        from sqlalchemy import func

        async with self._session(session) as s:
            stmt = select(
                RedemptionRequestRecord.state,
                func.count().label("cnt"),
            ).group_by(RedemptionRequestRecord.state)
            result = await s.execute(stmt)
            return {row.state: row.cnt for row in result}


class FundTermsRepository(BaseRepository):
    """CRUD for positions.fund_terms."""

    async def get_by_share_class(
        self, share_class: str, *, session: AsyncSession | None = None
    ) -> FundTermsRecord | None:
        async with self._session(session) as s:
            stmt = select(FundTermsRecord).where(
                FundTermsRecord.share_class == share_class
            )
            result = await s.execute(stmt)
            return result.scalar_one_or_none()

    async def get_all_active(
        self, *, session: AsyncSession | None = None
    ) -> list[FundTermsRecord]:
        async with self._session(session) as s:
            stmt = (
                select(FundTermsRecord)
                .where(FundTermsRecord.is_active.is_(True))
                .order_by(FundTermsRecord.share_class)
            )
            result = await s.execute(stmt)
            return list(result.scalars().all())

    async def upsert(
        self, record: FundTermsRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as s:
            merged = await s.merge(record)
            s.add(merged)
            await s.flush()


class InvestorKYCRepository(BaseRepository):
    """CRUD for platform.investor_kyc."""

    async def get_by_investor(
        self, investor_id: str, *, session: AsyncSession | None = None
    ) -> InvestorKYCRecord | None:
        async with self._session(session) as s:
            stmt = select(InvestorKYCRecord).where(
                InvestorKYCRecord.investor_id == investor_id
            )
            result = await s.execute(stmt)
            return result.scalar_one_or_none()

    async def upsert(
        self, record: InvestorKYCRecord, *, session: AsyncSession | None = None
    ) -> None:
        async with self._session(session) as s:
            merged = await s.merge(record)
            s.add(merged)
            await s.flush()
