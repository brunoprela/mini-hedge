"""Unit tests for investor operations services — tests workflow orchestration with mocked repos."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.investor_operations.core.state_machine import InvalidTransitionError
from app.modules.investor_operations.interfaces import (
    AMLStatus,
    KYCScreeningResult,
    KYCStatus,
    RedemptionState,
    SubscriptionState,
)
from app.modules.investor_operations.models.fund_terms import FundTermsRecord
from app.modules.investor_operations.models.redemption import RedemptionRequestRecord
from app.modules.investor_operations.models.subscription import SubscriptionRequestRecord
from app.modules.investor_operations.services import (
    InvestorKYCService,
    RedemptionService,
    SubscriptionService,
)


def _make_subscription_service(
    *,
    sub_repo: AsyncMock | None = None,
    terms_repo: AsyncMock | None = None,
    kyc_repo: AsyncMock | None = None,
    capital_service: AsyncMock | None = None,
    event_bus: AsyncMock | None = None,
) -> SubscriptionService:
    return SubscriptionService(
        subscription_repo=sub_repo or AsyncMock(),
        fund_terms_repo=terms_repo or AsyncMock(),
        kyc_repo=kyc_repo or AsyncMock(),
        capital_service=capital_service or AsyncMock(),
        event_bus=event_bus or AsyncMock(),
    )


def _make_redemption_service(
    *,
    red_repo: AsyncMock | None = None,
    terms_repo: AsyncMock | None = None,
    capital_service: AsyncMock | None = None,
    event_bus: AsyncMock | None = None,
) -> RedemptionService:
    return RedemptionService(
        redemption_repo=red_repo or AsyncMock(),
        fund_terms_repo=terms_repo or AsyncMock(),
        capital_service=capital_service or AsyncMock(),
        event_bus=event_bus or AsyncMock(),
    )


def _make_kyc_service(
    *,
    kyc_repo: AsyncMock | None = None,
    terms_repo: AsyncMock | None = None,
    kyc_adapter: AsyncMock | None = None,
) -> InvestorKYCService:
    return InvestorKYCService(
        kyc_repo=kyc_repo or AsyncMock(),
        fund_terms_repo=terms_repo or AsyncMock(),
        kyc_adapter=kyc_adapter or AsyncMock(),
    )


def _make_sub_record(
    *,
    state: str = "pending_kyc",
    investor_id: str | None = None,
    share_class: str = "default",
    amount: Decimal = Decimal("5000000"),
) -> SubscriptionRequestRecord:
    record = SubscriptionRequestRecord(
        investor_id=investor_id or str(uuid4()),
        share_class=share_class,
        requested_amount=amount,
        state=state,
    )
    record.id = str(uuid4())
    record.submitted_at = datetime.now(UTC)
    record.created_at = datetime.now(UTC)
    record.updated_at = datetime.now(UTC)
    return record


def _make_red_record(
    *,
    state: str = "pending_validation",
    investor_id: str | None = None,
    amount: Decimal = Decimal("1000000"),
) -> RedemptionRequestRecord:
    record = RedemptionRequestRecord(
        investor_id=investor_id or str(uuid4()),
        requested_amount=amount,
        state=state,
        notice_date=date.today(),
    )
    record.id = str(uuid4())
    record.submitted_at = datetime.now(UTC)
    record.created_at = datetime.now(UTC)
    record.updated_at = datetime.now(UTC)
    record.gate_applied = False
    return record


def _make_terms(
    share_class: str = "default",
) -> FundTermsRecord:
    record = FundTermsRecord(
        share_class=share_class,
        lock_up_months=12,
        notice_period_days=45,
        redemption_frequency="quarterly",
        gate_pct=Decimal("0.25"),
        minimum_subscription=Decimal("1000000"),
        minimum_redemption=Decimal("100000"),
        dealing_day=-1,
        payment_days=30,
        is_active=True,
    )
    record.id = str(uuid4())
    record.created_at = datetime.now(UTC)
    return record


class TestSubmitSubscription:
    @pytest.mark.asyncio
    async def test_creates_request_in_pending_kyc(self) -> None:
        sub_repo = AsyncMock()
        terms_repo = AsyncMock()
        terms_repo.get_by_share_class = AsyncMock(return_value=_make_terms())
        event_bus = AsyncMock()

        service = _make_subscription_service(
            sub_repo=sub_repo,
            terms_repo=terms_repo,
            event_bus=event_bus,
        )
        result = await service.submit_subscription(
            investor_id=str(uuid4()),
            amount=Decimal("5000000"),
        )

        assert result.state == SubscriptionState.PENDING_KYC
        sub_repo.insert.assert_called_once()
        event_bus.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_rejects_below_minimum(self) -> None:
        terms_repo = AsyncMock()
        terms_repo.get_by_share_class = AsyncMock(return_value=_make_terms())

        service = _make_subscription_service(terms_repo=terms_repo)
        with pytest.raises(ValueError, match="below minimum"):
            await service.submit_subscription(
                investor_id=str(uuid4()),
                amount=Decimal("500"),
            )


class TestKYCDecision:
    @pytest.mark.asyncio
    async def test_approve_transitions_to_kyc_approved(self) -> None:
        record = _make_sub_record(state="pending_kyc")
        sub_repo = AsyncMock()
        sub_repo.get_by_id = AsyncMock(return_value=record)

        service = _make_subscription_service(sub_repo=sub_repo)
        result = await service.record_kyc_decision(
            record.id, approved=True, decision_by="compliance@fund.com"
        )

        assert result.state == SubscriptionState.KYC_APPROVED
        sub_repo.update_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_reject_transitions_to_kyc_rejected(self) -> None:
        record = _make_sub_record(state="pending_kyc")
        sub_repo = AsyncMock()
        sub_repo.get_by_id = AsyncMock(return_value=record)

        service = _make_subscription_service(sub_repo=sub_repo)
        result = await service.record_kyc_decision(
            record.id, approved=False, decision_by="compliance@fund.com"
        )

        assert result.state == SubscriptionState.KYC_REJECTED

    @pytest.mark.asyncio
    async def test_not_found_raises(self) -> None:
        sub_repo = AsyncMock()
        sub_repo.get_by_id = AsyncMock(return_value=None)

        service = _make_subscription_service(sub_repo=sub_repo)
        with pytest.raises(ValueError, match="not found"):
            await service.record_kyc_decision(str(uuid4()), approved=True, decision_by="test")


class TestOpsReview:
    @pytest.mark.asyncio
    async def test_approve_transitions_to_pending_gp(self) -> None:
        record = _make_sub_record(state="kyc_approved")
        sub_repo = AsyncMock()
        sub_repo.get_by_id = AsyncMock(return_value=record)

        service = _make_subscription_service(sub_repo=sub_repo)
        result = await service.ops_review(record.id, approved=True, decision_by="ops@fund.com")

        assert result.state == SubscriptionState.PENDING_GP_APPROVAL


class TestGPDecision:
    @pytest.mark.asyncio
    async def test_approve_sets_dealing_date(self) -> None:
        record = _make_sub_record(state="pending_gp_approval")
        sub_repo = AsyncMock()
        sub_repo.get_by_id = AsyncMock(return_value=record)
        terms_repo = AsyncMock()
        terms_repo.get_by_share_class = AsyncMock(return_value=_make_terms())

        service = _make_subscription_service(sub_repo=sub_repo, terms_repo=terms_repo)
        result = await service.gp_decision(record.id, approved=True, decision_by="gp@fund.com")

        assert result.state == SubscriptionState.APPROVED
        # Dealing date should be set
        call_kwargs = sub_repo.update_state.call_args
        assert "dealing_date" in call_kwargs.kwargs

    @pytest.mark.asyncio
    async def test_reject(self) -> None:
        record = _make_sub_record(state="pending_gp_approval")
        sub_repo = AsyncMock()
        sub_repo.get_by_id = AsyncMock(return_value=record)

        service = _make_subscription_service(sub_repo=sub_repo)
        result = await service.gp_decision(record.id, approved=False, decision_by="gp@fund.com")

        assert result.state == SubscriptionState.REJECTED


class TestConfirmWire:
    @pytest.mark.asyncio
    async def test_transitions_to_queued(self) -> None:
        record = _make_sub_record(state="approved")
        sub_repo = AsyncMock()
        sub_repo.get_by_id = AsyncMock(return_value=record)

        service = _make_subscription_service(sub_repo=sub_repo)
        result = await service.confirm_wire(record.id, wire_reference="WIRE-123")

        assert result.state == SubscriptionState.QUEUED_FOR_NAV


class TestCancelSubscription:
    @pytest.mark.asyncio
    async def test_cancel_from_pending_kyc(self) -> None:
        record = _make_sub_record(state="pending_kyc")
        sub_repo = AsyncMock()
        sub_repo.get_by_id = AsyncMock(return_value=record)

        service = _make_subscription_service(sub_repo=sub_repo)
        result = await service.cancel_subscription(
            record.id, reason="Changed mind", cancelled_by="investor"
        )

        assert result.state == SubscriptionState.CANCELLED

    @pytest.mark.asyncio
    async def test_cannot_cancel_executed(self) -> None:
        record = _make_sub_record(state="executed")
        sub_repo = AsyncMock()
        sub_repo.get_by_id = AsyncMock(return_value=record)

        service = _make_subscription_service(sub_repo=sub_repo)
        with pytest.raises(InvalidTransitionError):
            await service.cancel_subscription(record.id, reason="Too late", cancelled_by="investor")


class TestSubmitRedemption:
    @pytest.mark.asyncio
    async def test_creates_request_in_pending_validation(self) -> None:
        red_repo = AsyncMock()
        event_bus = AsyncMock()

        service = _make_redemption_service(red_repo=red_repo, event_bus=event_bus)
        result = await service.submit_redemption(
            investor_id=str(uuid4()),
            amount=Decimal("1000000"),
        )

        assert result.state == RedemptionState.PENDING_VALIDATION
        red_repo.insert.assert_called_once()
        event_bus.publish.assert_called_once()


class TestValidateRedemption:
    @pytest.mark.asyncio
    async def test_valid_redemption(self) -> None:
        record = _make_red_record(state="pending_validation")
        red_repo = AsyncMock()
        red_repo.get_by_id = AsyncMock(return_value=record)
        terms_repo = AsyncMock()
        terms_repo.get_by_share_class = AsyncMock(return_value=_make_terms())

        service = _make_redemption_service(red_repo=red_repo, terms_repo=terms_repo)
        result = await service.validate_redemption(record.id)

        assert result.state == RedemptionState.VALIDATED

    @pytest.mark.asyncio
    async def test_below_minimum_fails(self) -> None:
        record = _make_red_record(state="pending_validation", amount=Decimal("50"))
        red_repo = AsyncMock()
        red_repo.get_by_id = AsyncMock(return_value=record)
        terms_repo = AsyncMock()
        terms_repo.get_by_share_class = AsyncMock(return_value=_make_terms())

        service = _make_redemption_service(red_repo=red_repo, terms_repo=terms_repo)
        result = await service.validate_redemption(record.id)

        assert result.state == RedemptionState.VALIDATION_FAILED


class TestScreenInvestor:
    @pytest.mark.asyncio
    async def test_approved_screening(self) -> None:
        kyc_adapter = AsyncMock()
        kyc_adapter.screen_investor = AsyncMock(
            return_value=KYCScreeningResult(
                approved=True,
                kyc_status=KYCStatus.APPROVED,
                aml_status=AMLStatus.CLEARED,
                sanctions_clear=True,
                pep_flag=False,
                source_of_funds_verified=True,
                screening_provider="mock-kyc",
            )
        )
        kyc_repo = AsyncMock()
        kyc_repo.get_by_investor = AsyncMock(return_value=None)

        service = _make_kyc_service(kyc_adapter=kyc_adapter, kyc_repo=kyc_repo)
        result = await service.screen_investor(
            investor_id=str(uuid4()),
            name="John Smith",
        )

        assert result.kyc_status == KYCStatus.APPROVED
        assert result.sanctions_clear is True
        kyc_repo.upsert.assert_called_once()


class TestConfirmPayment:
    @pytest.mark.asyncio
    async def test_transitions_to_executed(self) -> None:
        record = _make_red_record(state="pending_payment")
        red_repo = AsyncMock()
        red_repo.get_by_id = AsyncMock(return_value=record)

        service = _make_redemption_service(red_repo=red_repo)
        result = await service.confirm_payment(record.id, payment_reference="WIRE-RED-ABC")

        assert result.state == RedemptionState.EXECUTED
