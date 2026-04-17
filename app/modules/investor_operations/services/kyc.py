"""Investor KYC service — screening, fund terms management."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from app.shared.schema_registry import shared_topic

from app.modules.investor_operations.interfaces import (
    FundTermsSummary,
    InvestorKYCInfo,
    RedemptionFrequency,
)
from app.modules.investor_operations.models.fund_terms import FundTermsRecord
from app.modules.investor_operations.models.kyc import InvestorKYCRecord
from app.shared.audit.events import AuditEventType
from app.shared.events import BaseEvent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.investor_operations.repositories.fund_terms import FundTermsRepository
    from app.modules.investor_operations.repositories.kyc import InvestorKYCRepository
    from app.shared.adapters.kyc import KYCScreeningAdapter
    from app.shared.events import EventBus

_DEFAULT_SHARE_CLASS = "default"
_DEFAULT_REDEMPTION_FREQUENCY = "quarterly"
_DEFAULT_GATE_PCT = Decimal("0.25")
_DEFAULT_MIN_SUBSCRIPTION = Decimal("1000000")


def _now() -> datetime:
    return datetime.now(UTC)


class InvestorKYCService:
    """Handles KYC screening and fund terms management."""

    def __init__(
        self,
        *,
        kyc_repo: InvestorKYCRepository,
        fund_terms_repo: FundTermsRepository,
        kyc_adapter: KYCScreeningAdapter,
        event_bus: EventBus | None = None,
    ) -> None:
        self._kyc_repo = kyc_repo
        self._terms_repo = fund_terms_repo
        self._kyc_adapter = kyc_adapter
        self._event_bus = event_bus

    async def screen_investor(
        self,
        *,
        investor_id: str,
        name: str,
        entity_type: str = "individual",
        tax_jurisdiction: str | None = None,
        session: AsyncSession | None = None,
    ) -> InvestorKYCInfo:
        """Trigger KYC/AML screening via the adapter and persist results."""
        result = await self._kyc_adapter.screen_investor(
            investor_id=investor_id,
            name=name,
            entity_type=entity_type,
            tax_jurisdiction=tax_jurisdiction,
        )

        # Upsert KYC record
        existing = await self._kyc_repo.get_by_investor(investor_id, session=session)
        if existing:
            existing.kyc_status = result.kyc_status
            existing.aml_status = result.aml_status
            existing.sanctions_clear = result.sanctions_clear
            existing.pep_flag = result.pep_flag
            existing.source_of_funds_verified = result.source_of_funds_verified
            existing.screening_provider = result.screening_provider
            existing.last_screened_at = _now()
            existing.notes = result.notes
            await self._kyc_repo.upsert(existing, session=session)
            record = existing
        else:
            record = InvestorKYCRecord(
                investor_id=investor_id,
                kyc_status=result.kyc_status,
                aml_status=result.aml_status,
                sanctions_clear=result.sanctions_clear,
                pep_flag=result.pep_flag,
                source_of_funds_verified=result.source_of_funds_verified,
                screening_provider=result.screening_provider,
                last_screened_at=_now(),
                notes=result.notes,
            )
            await self._kyc_repo.upsert(record, session=session)

        info = InvestorKYCInfo(
            investor_id=UUID(investor_id),
            kyc_status=result.kyc_status,
            aml_status=result.aml_status,
            sanctions_clear=result.sanctions_clear,
            pep_flag=result.pep_flag,
            source_of_funds_verified=result.source_of_funds_verified,
            accredited_investor=bool(getattr(record, "accredited_investor", False)),
            last_screened_at=record.last_screened_at,
            screening_expires_at=record.screening_expires_at,
            screening_provider=result.screening_provider,
        )

        if self._event_bus is not None:
            await self._event_bus.publish(
                shared_topic("investor-operations"),
                BaseEvent(
                    event_type=AuditEventType.INVESTOR_KYC_SCREENED,
                    data={
                        "investor_id": investor_id,
                        "kyc_status": result.kyc_status,
                        "aml_status": result.aml_status,
                        "sanctions_clear": result.sanctions_clear,
                        "pep_flag": result.pep_flag,
                        "screening_provider": result.screening_provider,
                    },
                ),
            )

        return info

    async def get_investor_kyc(
        self,
        investor_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> InvestorKYCInfo | None:
        """Get the current KYC status for an investor."""
        record = await self._kyc_repo.get_by_investor(investor_id, session=session)
        if record is None:
            return None
        return InvestorKYCInfo(
            investor_id=UUID(record.investor_id),
            kyc_status=record.kyc_status,
            aml_status=record.aml_status,
            sanctions_clear=record.sanctions_clear,
            pep_flag=record.pep_flag,
            source_of_funds_verified=record.source_of_funds_verified,
            accredited_investor=record.accredited_investor,
            last_screened_at=record.last_screened_at,
            screening_expires_at=record.screening_expires_at,
            screening_provider=record.screening_provider,
        )

    async def get_fund_terms(
        self,
        share_class: str = _DEFAULT_SHARE_CLASS,
        *,
        session: AsyncSession | None = None,
    ) -> FundTermsSummary | None:
        record = await self._terms_repo.get_by_share_class(share_class, session=session)
        if record is None:
            return None
        return _terms_to_summary(record)

    async def list_fund_terms(
        self, *, session: AsyncSession | None = None
    ) -> list[FundTermsSummary]:
        records = await self._terms_repo.list_active(session=session)
        return [_terms_to_summary(r) for r in records]

    async def upsert_fund_terms(
        self,
        *,
        share_class: str,
        lock_up_months: int = 12,
        notice_period_days: int = 45,
        redemption_frequency: str = _DEFAULT_REDEMPTION_FREQUENCY,
        gate_pct: Decimal = _DEFAULT_GATE_PCT,
        minimum_subscription: Decimal = _DEFAULT_MIN_SUBSCRIPTION,
        minimum_redemption: Decimal = Decimal("100000"),
        dealing_day: int = -1,
        payment_days: int = 30,
        session: AsyncSession | None = None,
    ) -> FundTermsSummary:
        existing = await self._terms_repo.get_by_share_class(share_class, session=session)
        if existing:
            existing.lock_up_months = lock_up_months
            existing.notice_period_days = notice_period_days
            existing.redemption_frequency = redemption_frequency
            existing.gate_pct = gate_pct
            existing.minimum_subscription = minimum_subscription
            existing.minimum_redemption = minimum_redemption
            existing.dealing_day = dealing_day
            existing.payment_days = payment_days
            await self._terms_repo.upsert(existing, session=session)
            return _terms_to_summary(existing)

        record = FundTermsRecord(
            share_class=share_class,
            lock_up_months=lock_up_months,
            notice_period_days=notice_period_days,
            redemption_frequency=redemption_frequency,
            gate_pct=gate_pct,
            minimum_subscription=minimum_subscription,
            minimum_redemption=minimum_redemption,
            dealing_day=dealing_day,
            payment_days=payment_days,
        )
        await self._terms_repo.upsert(record, session=session)
        return _terms_to_summary(record)


# ---------------------------------------------------------------------------
#  Record -> DTO converter
# ---------------------------------------------------------------------------


def _terms_to_summary(record: FundTermsRecord) -> FundTermsSummary:
    return FundTermsSummary(
        id=UUID(record.id) if isinstance(record.id, str) else record.id,
        share_class=record.share_class,
        lock_up_months=record.lock_up_months,
        notice_period_days=record.notice_period_days,
        redemption_frequency=RedemptionFrequency(record.redemption_frequency),
        gate_pct=record.gate_pct,
        minimum_subscription=record.minimum_subscription,
        minimum_redemption=record.minimum_redemption,
        dealing_day=record.dealing_day,
        payment_days=record.payment_days,
        is_active=record.is_active,
    )
