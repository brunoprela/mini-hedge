"""Unit tests for investor_operations event publishing — verifies all state-changing methods emit events."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.investor_operations.interfaces import (
    RedemptionState,
    SubscriptionState,
)
from app.modules.investor_operations.services.kyc import InvestorKYCService
from app.modules.investor_operations.services.redemption import RedemptionService
from app.modules.investor_operations.services.subscription import SubscriptionService
from app.shared.audit.events import AuditEventType


def _make_sub_record(**overrides) -> MagicMock:
    r = MagicMock()
    r.id = "00000000-0000-0000-0000-000000000001"
    r.investor_id = "00000000-0000-0000-0000-000000000010"
    r.share_class = "default"
    r.requested_amount = Decimal("500000")
    r.state = SubscriptionState.PENDING_KYC
    r.submitted_at = datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)
    r.created_at = datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)
    r.updated_at = datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)
    r.kyc_decision_at = None
    r.kyc_decision_by = None
    r.kyc_notes = None
    r.ops_decision_at = None
    r.ops_decision_by = None
    r.ops_notes = None
    r.gp_decision_at = None
    r.gp_decision_by = None
    r.wire_confirmed_at = None
    r.wire_reference = None
    r.dealing_date = None
    r.executed_at = None
    r.nav_per_share = None
    r.shares_issued = None
    r.cancelled_at = None
    r.cancellation_reason = None
    for k, v in overrides.items():
        setattr(r, k, v)
    return r


def _make_red_record(**overrides) -> MagicMock:
    r = MagicMock()
    r.id = "00000000-0000-0000-0000-000000000002"
    r.investor_id = "00000000-0000-0000-0000-000000000010"
    r.requested_amount = Decimal("200000")
    r.approved_amount = None
    r.state = RedemptionState.PENDING_VALIDATION
    r.notice_date = date(2026, 4, 1)
    r.submitted_at = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
    r.created_at = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
    r.updated_at = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
    r.earliest_redemption_date = None
    r.lock_up_expiry_date = None
    r.gate_applied = False
    r.gate_pct = None
    r.dealing_date = None
    r.nav_per_share = None
    r.shares_redeemed = None
    r.payment_due_date = None
    r.payment_sent_at = None
    r.payment_reference = None
    r.cancelled_at = None
    r.cancellation_reason = None
    for k, v in overrides.items():
        setattr(r, k, v)
    return r


def _make_sub_service() -> tuple[SubscriptionService, AsyncMock]:
    event_bus = AsyncMock()
    sub_repo = AsyncMock()
    terms_repo = AsyncMock()
    terms_repo.get_by_share_class = AsyncMock(return_value=None)
    kyc_repo = AsyncMock()
    capital_service = AsyncMock()

    service = SubscriptionService(
        subscription_repo=sub_repo,
        fund_terms_repo=terms_repo,
        kyc_repo=kyc_repo,
        capital_service=capital_service,
        event_bus=event_bus,
    )
    return service, event_bus


def _make_red_service() -> tuple[RedemptionService, AsyncMock]:
    event_bus = AsyncMock()
    red_repo = AsyncMock()
    terms_repo = AsyncMock()
    terms_repo.get_by_share_class = AsyncMock(return_value=None)
    capital_service = AsyncMock()

    service = RedemptionService(
        redemption_repo=red_repo,
        fund_terms_repo=terms_repo,
        capital_service=capital_service,
        event_bus=event_bus,
    )
    return service, event_bus


class TestSubscriptionOpsReviewEvent:
    @pytest.mark.asyncio
    async def test_ops_review_publishes_event(self) -> None:
        service, event_bus = _make_sub_service()
        record = _make_sub_record(state=SubscriptionState.KYC_APPROVED)
        service._subscription_repo.get_by_id = AsyncMock(return_value=record)

        await service.ops_review("00000000-0000-0000-0000-000000000001", approved=True, decision_by="ops-1")

        # Should publish at least ops_reviewed event
        calls = [c for c in event_bus.publish.call_args_list
                 if c.args[1].event_type == AuditEventType.SUBSCRIPTION_OPS_REVIEWED]
        assert len(calls) == 1
        assert calls[0].args[1].data["approved"] is True


class TestSubscriptionGpDecisionEvent:
    @pytest.mark.asyncio
    async def test_gp_decision_publishes_event(self) -> None:
        service, event_bus = _make_sub_service()
        record = _make_sub_record(state=SubscriptionState.PENDING_GP_APPROVAL)
        service._subscription_repo.get_by_id = AsyncMock(return_value=record)

        await service.gp_decision("00000000-0000-0000-0000-000000000001", approved=True, decision_by="gp-1")

        calls = [c for c in event_bus.publish.call_args_list
                 if c.args[1].event_type == AuditEventType.SUBSCRIPTION_GP_DECIDED]
        assert len(calls) == 1
        assert calls[0].args[1].data["decision_by"] == "gp-1"


class TestSubscriptionWireConfirmedEvent:
    @pytest.mark.asyncio
    async def test_confirm_wire_publishes_event(self) -> None:
        service, event_bus = _make_sub_service()
        record = _make_sub_record(state=SubscriptionState.APPROVED)
        service._subscription_repo.get_by_id = AsyncMock(return_value=record)

        await service.confirm_wire("00000000-0000-0000-0000-000000000001", wire_reference="WIRE-123")

        calls = [c for c in event_bus.publish.call_args_list
                 if c.args[1].event_type == AuditEventType.SUBSCRIPTION_WIRE_CONFIRMED]
        assert len(calls) == 1
        assert calls[0].args[1].data["wire_reference"] == "WIRE-123"


class TestSubscriptionCancelledEvent:
    @pytest.mark.asyncio
    async def test_cancel_publishes_event(self) -> None:
        service, event_bus = _make_sub_service()
        record = _make_sub_record(state=SubscriptionState.PENDING_KYC)
        service._subscription_repo.get_by_id = AsyncMock(return_value=record)

        await service.cancel_subscription("00000000-0000-0000-0000-000000000001", reason="changed mind", cancelled_by="00000000-0000-0000-0000-000000000010")

        calls = [c for c in event_bus.publish.call_args_list
                 if c.args[1].event_type == AuditEventType.SUBSCRIPTION_CANCELLED]
        assert len(calls) == 1
        assert calls[0].args[1].data["reason"] == "changed mind"


class TestRedemptionValidatedEvent:
    @pytest.mark.asyncio
    async def test_validate_publishes_event(self) -> None:
        service, event_bus = _make_red_service()
        record = _make_red_record(state=RedemptionState.PENDING_VALIDATION)
        service._redemption_repo.get_by_id = AsyncMock(return_value=record)

        await service.validate_redemption("00000000-0000-0000-0000-000000000002")

        calls = [c for c in event_bus.publish.call_args_list
                 if c.args[1].event_type == AuditEventType.REDEMPTION_VALIDATED]
        assert len(calls) == 1
        assert calls[0].args[1].data["validated"] is True


class TestRedemptionPaymentConfirmedEvent:
    @pytest.mark.asyncio
    async def test_confirm_payment_publishes_event(self) -> None:
        service, event_bus = _make_red_service()
        record = _make_red_record(state=RedemptionState.PENDING_PAYMENT)
        service._redemption_repo.get_by_id = AsyncMock(return_value=record)

        await service.confirm_payment("00000000-0000-0000-0000-000000000002", payment_reference="PAY-456")

        calls = [c for c in event_bus.publish.call_args_list
                 if c.args[1].event_type == AuditEventType.REDEMPTION_PAYMENT_CONFIRMED]
        assert len(calls) == 1
        assert calls[0].args[1].data["payment_reference"] == "PAY-456"


class TestRedemptionCancelledEvent:
    @pytest.mark.asyncio
    async def test_cancel_publishes_event(self) -> None:
        service, event_bus = _make_red_service()
        record = _make_red_record(state=RedemptionState.PENDING_VALIDATION)
        service._redemption_repo.get_by_id = AsyncMock(return_value=record)

        await service.cancel_redemption("00000000-0000-0000-0000-000000000002", reason="duplicate", cancelled_by="ops-1")

        calls = [c for c in event_bus.publish.call_args_list
                 if c.args[1].event_type == AuditEventType.REDEMPTION_CANCELLED]
        assert len(calls) == 1
        assert calls[0].args[1].data["reason"] == "duplicate"


class TestKYCScreeningEvent:
    @pytest.mark.asyncio
    async def test_screen_investor_publishes_event(self) -> None:
        event_bus = AsyncMock()
        kyc_repo = AsyncMock()
        kyc_repo.get_by_investor = AsyncMock(return_value=None)
        kyc_repo.upsert = AsyncMock()
        terms_repo = AsyncMock()

        # Mock KYC adapter
        kyc_adapter = AsyncMock()
        screening_result = MagicMock()
        screening_result.kyc_status = "approved"
        screening_result.aml_status = "cleared"
        screening_result.sanctions_clear = True
        screening_result.pep_flag = False
        screening_result.source_of_funds_verified = True
        screening_result.screening_provider = "test-provider"
        screening_result.notes = ""
        kyc_adapter.screen_investor = AsyncMock(return_value=screening_result)

        service = InvestorKYCService(
            kyc_repo=kyc_repo,
            fund_terms_repo=terms_repo,
            kyc_adapter=kyc_adapter,
            event_bus=event_bus,
        )

        await service.screen_investor(investor_id="00000000-0000-0000-0000-000000000010", name="Test Investor")

        event_bus.publish.assert_called_once()
        _, event = event_bus.publish.call_args.args
        assert event.event_type == AuditEventType.INVESTOR_KYC_SCREENED
        assert event.data["investor_id"] == "00000000-0000-0000-0000-000000000010"
        assert event.data["kyc_status"] == "approved"

    @pytest.mark.asyncio
    async def test_screen_no_event_without_bus(self) -> None:
        kyc_repo = AsyncMock()
        kyc_repo.get_by_investor = AsyncMock(return_value=None)
        kyc_repo.upsert = AsyncMock()
        terms_repo = AsyncMock()

        kyc_adapter = AsyncMock()
        screening_result = MagicMock()
        screening_result.kyc_status = "approved"
        screening_result.aml_status = "cleared"
        screening_result.sanctions_clear = True
        screening_result.pep_flag = False
        screening_result.source_of_funds_verified = True
        screening_result.screening_provider = "test-provider"
        screening_result.notes = ""
        kyc_adapter.screen_investor = AsyncMock(return_value=screening_result)

        service = InvestorKYCService(
            kyc_repo=kyc_repo,
            fund_terms_repo=terms_repo,
            kyc_adapter=kyc_adapter,
        )

        # Should not raise
        result = await service.screen_investor(investor_id="00000000-0000-0000-0000-000000000010", name="Test Investor")
        assert result is not None
