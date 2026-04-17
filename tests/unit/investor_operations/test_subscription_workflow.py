"""Unit tests for SubscriptionService — full lifecycle workflow tests."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.modules.investor_operations.interfaces import SubscriptionState
from app.modules.investor_operations.services.subscription import SubscriptionService

_REQ_ID = "00000000-0000-0000-0000-000000000001"
_INV_ID = "00000000-0000-0000-0000-000000000010"
_PORT_ID = UUID("00000000-0000-0000-0000-000000000002")


def _make_sub_record(**overrides) -> MagicMock:
    r = MagicMock()
    r.id = _REQ_ID
    r.investor_id = _INV_ID
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


def _make_service() -> tuple[SubscriptionService, AsyncMock, AsyncMock]:
    event_bus = AsyncMock()
    sub_repo = AsyncMock()
    sub_repo.insert = AsyncMock()
    sub_repo.update_state = AsyncMock()
    sub_repo.list_by_dealing_date = AsyncMock(return_value=[])
    terms_repo = AsyncMock()
    terms_repo.get_by_share_class = AsyncMock(return_value=None)
    kyc_repo = AsyncMock()
    capital_service = AsyncMock()

    svc = SubscriptionService(
        subscription_repo=sub_repo,
        fund_terms_repo=terms_repo,
        kyc_repo=kyc_repo,
        capital_service=capital_service,
        event_bus=event_bus,
    )
    return svc, event_bus, capital_service


class TestSubmitSubscription:
    @pytest.mark.asyncio
    async def test_submit_creates_pending_kyc(self) -> None:
        svc, event_bus, _ = _make_service()

        result = await svc.submit_subscription(
            investor_id=_INV_ID, amount=Decimal("500000")
        )

        assert result.state == SubscriptionState.PENDING_KYC
        assert result.requested_amount == Decimal("500000")
        svc._subscription_repo.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_rejects_below_minimum(self) -> None:
        svc, _, _ = _make_service()
        terms = MagicMock()
        terms.minimum_subscription = Decimal("1000000")
        svc._terms_repo.get_by_share_class = AsyncMock(return_value=terms)

        with pytest.raises(ValueError, match="below minimum"):
            await svc.submit_subscription(
                investor_id=_INV_ID, amount=Decimal("100000")
            )


class TestKYCDecision:
    @pytest.mark.asyncio
    async def test_kyc_approved(self) -> None:
        svc, _, _ = _make_service()
        record = _make_sub_record(state=SubscriptionState.PENDING_KYC)
        svc._subscription_repo.get_by_id = AsyncMock(return_value=record)

        result = await svc.record_kyc_decision(
            _REQ_ID, approved=True, decision_by="kyc-analyst"
        )

        assert result.state == SubscriptionState.KYC_APPROVED

    @pytest.mark.asyncio
    async def test_kyc_rejected(self) -> None:
        svc, _, _ = _make_service()
        record = _make_sub_record(state=SubscriptionState.PENDING_KYC)
        svc._subscription_repo.get_by_id = AsyncMock(return_value=record)

        result = await svc.record_kyc_decision(
            _REQ_ID, approved=False, decision_by="kyc-analyst"
        )

        assert result.state == SubscriptionState.KYC_REJECTED

    @pytest.mark.asyncio
    async def test_kyc_not_found_raises(self) -> None:
        svc, _, _ = _make_service()
        svc._subscription_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await svc.record_kyc_decision(_REQ_ID, approved=True, decision_by="x")


class TestOpsReview:
    @pytest.mark.asyncio
    async def test_ops_approved_transitions_to_gp(self) -> None:
        svc, _, _ = _make_service()
        record = _make_sub_record(state=SubscriptionState.KYC_APPROVED)
        svc._subscription_repo.get_by_id = AsyncMock(return_value=record)

        result = await svc.ops_review(_REQ_ID, approved=True, decision_by="ops-1")

        assert result.state == SubscriptionState.PENDING_GP_APPROVAL

    @pytest.mark.asyncio
    async def test_ops_rejected_cancels(self) -> None:
        svc, _, _ = _make_service()
        record = _make_sub_record(state=SubscriptionState.KYC_APPROVED)
        svc._subscription_repo.get_by_id = AsyncMock(return_value=record)

        result = await svc.ops_review(_REQ_ID, approved=False, decision_by="ops-1")

        assert result.state == SubscriptionState.CANCELLED


class TestGPDecision:
    @pytest.mark.asyncio
    async def test_gp_approved(self) -> None:
        svc, _, _ = _make_service()
        record = _make_sub_record(state=SubscriptionState.PENDING_GP_APPROVAL)
        svc._subscription_repo.get_by_id = AsyncMock(return_value=record)

        result = await svc.gp_decision(_REQ_ID, approved=True, decision_by="gp-1")

        assert result.state == SubscriptionState.APPROVED

    @pytest.mark.asyncio
    async def test_gp_rejected(self) -> None:
        svc, _, _ = _make_service()
        record = _make_sub_record(state=SubscriptionState.PENDING_GP_APPROVAL)
        svc._subscription_repo.get_by_id = AsyncMock(return_value=record)

        result = await svc.gp_decision(_REQ_ID, approved=False, decision_by="gp-1")

        assert result.state == SubscriptionState.REJECTED


class TestConfirmWire:
    @pytest.mark.asyncio
    async def test_wire_transitions_to_queued(self) -> None:
        svc, _, _ = _make_service()
        record = _make_sub_record(state=SubscriptionState.APPROVED)
        svc._subscription_repo.get_by_id = AsyncMock(return_value=record)

        result = await svc.confirm_wire(_REQ_ID, wire_reference="WIRE-123")

        assert result.state == SubscriptionState.QUEUED_FOR_NAV
        assert result.wire_reference == "WIRE-123"


class TestExecuteSubscriptions:
    @pytest.mark.asyncio
    async def test_executes_queued_subscriptions(self) -> None:
        svc, _, capital_service = _make_service()
        record = _make_sub_record(state=SubscriptionState.QUEUED_FOR_NAV)
        svc._subscription_repo.list_by_dealing_date = AsyncMock(return_value=[record])

        results = await svc.execute_subscriptions(
            dealing_date=date(2026, 4, 15),
            nav_per_share=Decimal("1000"),
            portfolio_id=_PORT_ID,
        )

        assert len(results) == 1
        assert results[0].state == SubscriptionState.EXECUTED
        assert results[0].nav_per_share == Decimal("1000")
        assert results[0].shares_issued == Decimal("500.000000")  # 500000 / 1000
        capital_service.process_subscription.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_non_queued(self) -> None:
        svc, _, capital_service = _make_service()
        record = _make_sub_record(state=SubscriptionState.APPROVED)
        svc._subscription_repo.list_by_dealing_date = AsyncMock(return_value=[record])

        results = await svc.execute_subscriptions(
            dealing_date=date(2026, 4, 15),
            nav_per_share=Decimal("1000"),
            portfolio_id=_PORT_ID,
        )

        assert results == []
        capital_service.process_subscription.assert_not_called()


class TestCancelSubscription:
    @pytest.mark.asyncio
    async def test_cancel_from_pending_kyc(self) -> None:
        svc, _, _ = _make_service()
        record = _make_sub_record(state=SubscriptionState.PENDING_KYC)
        svc._subscription_repo.get_by_id = AsyncMock(return_value=record)

        result = await svc.cancel_subscription(
            _REQ_ID, reason="changed mind", cancelled_by=_INV_ID
        )

        assert result.state == SubscriptionState.CANCELLED
        assert result.cancellation_reason == "changed mind"

    @pytest.mark.asyncio
    async def test_cancel_not_found_raises(self) -> None:
        svc, _, _ = _make_service()
        svc._subscription_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await svc.cancel_subscription(_REQ_ID, reason="test", cancelled_by="x")


class TestFullWorkflow:
    """Test the happy path through the entire subscription lifecycle."""

    @pytest.mark.asyncio
    async def test_full_happy_path(self) -> None:
        svc, event_bus, capital_service = _make_service()

        # 1. Submit
        result = await svc.submit_subscription(
            investor_id=_INV_ID, amount=Decimal("500000")
        )
        assert result.state == SubscriptionState.PENDING_KYC
        req_id = str(result.id)

        # Mock get_by_id for subsequent steps
        def _get_record(**overrides):
            r = _make_sub_record(id=req_id, **overrides)
            return AsyncMock(return_value=r)

        # 2. KYC approval
        svc._subscription_repo.get_by_id = _get_record(state=SubscriptionState.PENDING_KYC)
        result = await svc.record_kyc_decision(req_id, approved=True, decision_by="kyc-1")
        assert result.state == SubscriptionState.KYC_APPROVED

        # 3. Ops review
        svc._subscription_repo.get_by_id = _get_record(state=SubscriptionState.KYC_APPROVED)
        result = await svc.ops_review(req_id, approved=True, decision_by="ops-1")
        assert result.state == SubscriptionState.PENDING_GP_APPROVAL

        # 4. GP approval
        svc._subscription_repo.get_by_id = _get_record(state=SubscriptionState.PENDING_GP_APPROVAL)
        result = await svc.gp_decision(req_id, approved=True, decision_by="gp-1")
        assert result.state == SubscriptionState.APPROVED

        # 5. Wire confirmation
        svc._subscription_repo.get_by_id = _get_record(state=SubscriptionState.APPROVED)
        result = await svc.confirm_wire(req_id, wire_reference="WIRE-456")
        assert result.state == SubscriptionState.QUEUED_FOR_NAV

        # 6. Execution
        queued_record = _make_sub_record(id=req_id, state=SubscriptionState.QUEUED_FOR_NAV)
        svc._subscription_repo.list_by_dealing_date = AsyncMock(return_value=[queued_record])
        results = await svc.execute_subscriptions(
            dealing_date=date(2026, 4, 15),
            nav_per_share=Decimal("1000"),
            portfolio_id=_PORT_ID,
        )
        assert len(results) == 1
        assert results[0].state == SubscriptionState.EXECUTED

        # 6 lifecycle steps: submit, kyc, ops, gp, wire, execute
        assert event_bus.publish.call_count == 6
