"""Unit tests for RedemptionService — full lifecycle workflow tests."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.modules.investor_operations.interfaces import RedemptionState
from app.modules.investor_operations.services.redemption import RedemptionService

_REQ_ID = "00000000-0000-0000-0000-000000000001"
_INV_ID = "00000000-0000-0000-0000-000000000010"
_PORT_ID = UUID("00000000-0000-0000-0000-000000000002")


def _make_red_record(**overrides) -> MagicMock:
    r = MagicMock()
    r.id = _REQ_ID
    r.investor_id = _INV_ID
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
    r.share_class = "default"
    for k, v in overrides.items():
        setattr(r, k, v)
    return r


def _make_service() -> tuple[RedemptionService, AsyncMock, AsyncMock]:
    event_bus = AsyncMock()
    red_repo = AsyncMock()
    red_repo.insert = AsyncMock()
    red_repo.update_state = AsyncMock()
    red_repo.list_by_state = AsyncMock(return_value=[])
    red_repo.list_by_dealing_date = AsyncMock(return_value=[])
    terms_repo = AsyncMock()
    terms_repo.get_by_share_class = AsyncMock(return_value=None)
    capital_service = AsyncMock()

    svc = RedemptionService(
        redemption_repo=red_repo,
        fund_terms_repo=terms_repo,
        capital_service=capital_service,
        event_bus=event_bus,
    )
    return svc, event_bus, capital_service


class TestSubmitRedemption:
    @pytest.mark.asyncio
    async def test_submit_creates_pending_validation(self) -> None:
        svc, _, _ = _make_service()

        result = await svc.submit_redemption(
            investor_id=_INV_ID, amount=Decimal("200000")
        )

        assert result.state == RedemptionState.PENDING_VALIDATION
        assert result.requested_amount == Decimal("200000")
        svc._redemption_repo.insert.assert_called_once()


class TestValidateRedemption:
    @pytest.mark.asyncio
    async def test_validates_successfully(self) -> None:
        svc, _, _ = _make_service()
        record = _make_red_record(state=RedemptionState.PENDING_VALIDATION)
        svc._redemption_repo.get_by_id = AsyncMock(return_value=record)

        result = await svc.validate_redemption(_REQ_ID)

        assert result.state == RedemptionState.VALIDATED

    @pytest.mark.asyncio
    async def test_validation_fails_below_minimum(self) -> None:
        svc, _, _ = _make_service()
        terms = MagicMock()
        terms.lock_up_months = 0
        terms.notice_period_days = 30
        terms.minimum_redemption = Decimal("500000")  # higher than requested 200k
        terms.redemption_frequency = "quarterly"
        terms.dealing_day = 1
        svc._terms_repo.get_by_share_class = AsyncMock(return_value=terms)

        record = _make_red_record(
            state=RedemptionState.PENDING_VALIDATION,
            requested_amount=Decimal("200000"),
        )
        svc._redemption_repo.get_by_id = AsyncMock(return_value=record)

        result = await svc.validate_redemption(_REQ_ID)

        assert result.state == RedemptionState.VALIDATION_FAILED

    @pytest.mark.asyncio
    async def test_validate_not_found_raises(self) -> None:
        svc, _, _ = _make_service()
        svc._redemption_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await svc.validate_redemption(_REQ_ID)


class TestGateCheck:
    @pytest.mark.asyncio
    async def test_no_gate_queues_for_nav(self) -> None:
        svc, _, _ = _make_service()
        records = [_make_red_record(state=RedemptionState.VALIDATED)]
        svc._redemption_repo.list_by_state = AsyncMock(return_value=records)

        result = await svc.run_gate_check(
            dealing_date=date(2026, 4, 15), fund_nav=Decimal("50000000")
        )

        # Without fund terms defining a gate, requests pass through
        assert result is not None


class TestConfirmPayment:
    @pytest.mark.asyncio
    async def test_confirm_payment_transitions_to_executed(self) -> None:
        svc, _, _ = _make_service()
        record = _make_red_record(state=RedemptionState.PENDING_PAYMENT)
        svc._redemption_repo.get_by_id = AsyncMock(return_value=record)

        result = await svc.confirm_payment(_REQ_ID, payment_reference="PAY-789")

        assert result.state == RedemptionState.EXECUTED


class TestCancelRedemption:
    @pytest.mark.asyncio
    async def test_cancel_from_pending(self) -> None:
        svc, _, _ = _make_service()
        record = _make_red_record(state=RedemptionState.PENDING_VALIDATION)
        svc._redemption_repo.get_by_id = AsyncMock(return_value=record)

        result = await svc.cancel_redemption(_REQ_ID, reason="duplicate", cancelled_by="ops-1")

        assert result.state == RedemptionState.CANCELLED
        assert result.cancellation_reason == "duplicate"

    @pytest.mark.asyncio
    async def test_cancel_not_found_raises(self) -> None:
        svc, _, _ = _make_service()
        svc._redemption_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await svc.cancel_redemption(_REQ_ID, reason="test", cancelled_by="x")


class TestExecuteRedemptions:
    @pytest.mark.asyncio
    async def test_executes_queued_redemptions(self) -> None:
        svc, _, capital_service = _make_service()
        record = _make_red_record(state=RedemptionState.QUEUED_FOR_NAV)
        svc._redemption_repo.list_by_dealing_date = AsyncMock(return_value=[record])

        results = await svc.execute_redemptions(
            dealing_date=date(2026, 4, 15),
            nav_per_share=Decimal("1000"),
            portfolio_id=_PORT_ID,
        )

        assert len(results) == 1
        assert results[0].state == RedemptionState.PENDING_PAYMENT
        capital_service.process_redemption.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_non_queued(self) -> None:
        svc, _, capital_service = _make_service()
        record = _make_red_record(state=RedemptionState.VALIDATED)
        svc._redemption_repo.list_by_dealing_date = AsyncMock(return_value=[record])

        results = await svc.execute_redemptions(
            dealing_date=date(2026, 4, 15),
            nav_per_share=Decimal("1000"),
            portfolio_id=_PORT_ID,
        )

        assert results == []
        capital_service.process_redemption.assert_not_called()
