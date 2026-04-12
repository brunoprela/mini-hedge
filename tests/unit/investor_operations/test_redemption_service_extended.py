"""Extended tests for RedemptionService — covers lock-up, gate check, execute gate_applied,
get/list/queue_summary methods."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.modules.investor_operations.interfaces import (
    RedemptionState,
)
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
    for k, v in overrides.items():
        setattr(r, k, v)
    return r


def _make_terms(**overrides) -> MagicMock:
    t = MagicMock()
    t.lock_up_months = 12
    t.notice_period_days = 45
    t.minimum_redemption = Decimal("100000")
    t.redemption_frequency = "quarterly"
    t.dealing_day = -1
    t.payment_days = 30
    t.gate_pct = Decimal("0.25")
    for k, v in overrides.items():
        setattr(t, k, v)
    return t


def _make_service(
    *,
    red_repo: AsyncMock | None = None,
    terms_repo: AsyncMock | None = None,
    capital_service: AsyncMock | None = None,
    event_bus: AsyncMock | None = None,
) -> RedemptionService:
    _red_repo = red_repo or AsyncMock()
    _terms_repo = terms_repo or AsyncMock()
    _terms_repo.get_by_share_class = getattr(
        _terms_repo, "get_by_share_class", AsyncMock(return_value=None)
    )
    return RedemptionService(
        redemption_repo=_red_repo,
        fund_terms_repo=_terms_repo,
        capital_service=capital_service or AsyncMock(),
        event_bus=event_bus or AsyncMock(),
    )


class TestValidateLockUp:
    """Covers lines 137-142, 161: lock-up validation failure path."""

    @pytest.mark.asyncio
    async def test_lock_up_not_expired_fails_validation(self) -> None:
        record = _make_red_record(state=RedemptionState.PENDING_VALIDATION)
        red_repo = AsyncMock()
        red_repo.get_by_id = AsyncMock(return_value=record)
        red_repo.update_state = AsyncMock()

        terms = _make_terms(lock_up_months=120)  # 10 years — won't expire
        terms_repo = AsyncMock()
        terms_repo.get_by_share_class = AsyncMock(return_value=terms)

        service = _make_service(red_repo=red_repo, terms_repo=terms_repo)
        result = await service.validate_redemption(
            _REQ_ID,
            subscription_date=date(2025, 1, 1),  # recent subscription
        )

        assert result.state == RedemptionState.VALIDATION_FAILED


class TestRunGateCheck:
    """Covers lines 196-221, 224: gate triggered and no-gate paths with pending records."""

    @pytest.mark.asyncio
    async def test_gate_triggered_applies_pro_rata(self) -> None:
        """When total requested > gate capacity, gate triggers and pro-rata applies."""
        r1 = _make_red_record(
            id="00000000-0000-0000-0000-000000000011",
            state=RedemptionState.VALIDATED,
            requested_amount=Decimal("6000000"),
        )
        r2 = _make_red_record(
            id="00000000-0000-0000-0000-000000000012",
            state=RedemptionState.VALIDATED,
            requested_amount=Decimal("4000000"),
        )
        red_repo = AsyncMock()
        red_repo.list_pending_for_gate = AsyncMock(return_value=[r1, r2])
        red_repo.update_state = AsyncMock()

        event_bus = AsyncMock()

        service = _make_service(red_repo=red_repo, event_bus=event_bus)
        # Fund NAV of 10M with 25% gate = 2.5M capacity but 10M requested
        result = await service.run_gate_check(
            dealing_date=date(2026, 6, 30),
            fund_nav=Decimal("10000000"),
            gate_pct=Decimal("0.25"),
        )

        assert result.gate_triggered is True
        assert result.total_requested == Decimal("10000000")
        assert result.gate_capacity == Decimal("2500000")
        # Both requests should have been processed
        assert red_repo.update_state.call_count == 2
        # Gate event should be published
        event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_no_gate_queues_for_nav(self) -> None:
        """When total requested <= gate capacity, no gate triggered."""
        r1 = _make_red_record(
            id="00000000-0000-0000-0000-000000000011",
            state=RedemptionState.VALIDATED,
            requested_amount=Decimal("100000"),
        )
        red_repo = AsyncMock()
        red_repo.list_pending_for_gate = AsyncMock(return_value=[r1])
        red_repo.update_state = AsyncMock()

        service = _make_service(red_repo=red_repo)
        result = await service.run_gate_check(
            dealing_date=date(2026, 6, 30),
            fund_nav=Decimal("10000000"),
            gate_pct=Decimal("0.25"),
        )

        assert result.gate_triggered is False

    @pytest.mark.asyncio
    async def test_gate_check_uses_terms_when_no_pct_given(self) -> None:
        """When gate_pct is None, looks up fund terms."""
        red_repo = AsyncMock()
        red_repo.list_pending_for_gate = AsyncMock(return_value=[])

        terms = _make_terms(gate_pct=Decimal("0.10"))
        terms_repo = AsyncMock()
        terms_repo.get_by_share_class = AsyncMock(return_value=terms)

        service = _make_service(red_repo=red_repo, terms_repo=terms_repo)
        result = await service.run_gate_check(
            dealing_date=date(2026, 6, 30),
            fund_nav=Decimal("10000000"),
        )

        # Should use terms.gate_pct = 0.10
        assert result.gate_capacity == Decimal("1000000")


class TestExecuteRedemptionsGateApplied:
    """Covers lines 259-265: gate_applied records transition through queued_for_nav."""

    @pytest.mark.asyncio
    async def test_gate_applied_transitions_through_queued(self) -> None:
        record = _make_red_record(
            state=RedemptionState.GATE_APPLIED,
            approved_amount=Decimal("150000"),
        )
        red_repo = AsyncMock()
        red_repo.list_by_dealing_date = AsyncMock(return_value=[record])
        red_repo.update_state = AsyncMock()

        terms = _make_terms(payment_days=30)
        terms_repo = AsyncMock()
        terms_repo.get_by_share_class = AsyncMock(return_value=terms)

        capital_service = AsyncMock()

        service = _make_service(
            red_repo=red_repo,
            terms_repo=terms_repo,
            capital_service=capital_service,
        )
        results = await service.execute_redemptions(
            dealing_date=date(2026, 6, 30),
            nav_per_share=Decimal("1000"),
            portfolio_id=_PORT_ID,
        )

        assert len(results) == 1
        assert results[0].state == RedemptionState.PENDING_PAYMENT
        capital_service.process_redemption.assert_called_once()
        # Should have called update_state at least twice:
        # once for GATE_APPLIED -> QUEUED_FOR_NAV, once for final PENDING_PAYMENT
        assert red_repo.update_state.call_count >= 2


class TestConfirmPaymentNotFound:
    """Covers lines 335-336."""

    @pytest.mark.asyncio
    async def test_not_found_raises(self) -> None:
        red_repo = AsyncMock()
        red_repo.get_by_id = AsyncMock(return_value=None)

        service = _make_service(red_repo=red_repo)
        with pytest.raises(ValueError, match="not found"):
            await service.confirm_payment(_REQ_ID, payment_reference="PAY-999")


class TestGetRedemption:
    """Covers lines 411-412."""

    @pytest.mark.asyncio
    async def test_returns_summary_when_found(self) -> None:
        record = _make_red_record()
        red_repo = AsyncMock()
        red_repo.get_by_id = AsyncMock(return_value=record)

        service = _make_service(red_repo=red_repo)
        result = await service.get_redemption(_REQ_ID)

        assert result is not None
        assert result.requested_amount == Decimal("200000")

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        red_repo = AsyncMock()
        red_repo.get_by_id = AsyncMock(return_value=None)

        service = _make_service(red_repo=red_repo)
        result = await service.get_redemption(_REQ_ID)

        assert result is None


class TestListRedemptions:
    """Covers lines 421-437: by state, by investor, default paths."""

    @pytest.mark.asyncio
    async def test_list_by_state(self) -> None:
        records = [_make_red_record(), _make_red_record(id="00000000-0000-0000-0000-000000000099")]
        red_repo = AsyncMock()
        red_repo.list_by_state = AsyncMock(return_value=records)

        service = _make_service(red_repo=red_repo)
        result = await service.list_redemptions(state="pending_validation")

        assert len(result) == 2
        red_repo.list_by_state.assert_called_once_with("pending_validation", session=None)

    @pytest.mark.asyncio
    async def test_list_by_investor(self) -> None:
        records = [_make_red_record()]
        red_repo = AsyncMock()
        red_repo.list_by_investor = AsyncMock(return_value=records)

        service = _make_service(red_repo=red_repo)
        result = await service.list_redemptions(investor_id=_INV_ID)

        assert len(result) == 1
        red_repo.list_by_investor.assert_called_once_with(_INV_ID, session=None)

    @pytest.mark.asyncio
    async def test_list_default_all_pending_states(self) -> None:
        red_repo = AsyncMock()
        red_repo.list_by_state = AsyncMock(return_value=[])

        service = _make_service(red_repo=red_repo)
        result = await service.list_redemptions()

        assert result == []
        # Should call list_by_state for each pending state
        assert red_repo.list_by_state.call_count == 7


class TestGetQueueSummary:
    """Covers lines 449-477."""

    @pytest.mark.asyncio
    async def test_queue_summary_with_terms(self) -> None:
        red_repo = AsyncMock()
        red_repo.count_by_state = AsyncMock(
            return_value={
                RedemptionState.PENDING_VALIDATION: 2,
                RedemptionState.VALIDATED: 1,
                RedemptionState.EXECUTED: 5,
            }
        )
        red_repo.list_by_state = AsyncMock(return_value=[])

        terms = _make_terms()
        terms_repo = AsyncMock()
        terms_repo.get_by_share_class = AsyncMock(return_value=terms)

        service = _make_service(red_repo=red_repo, terms_repo=terms_repo)
        result = await service.get_queue_summary()

        assert result.pending_redemptions == 3  # 2 pending_validation + 1 validated
        assert result.pending_subscriptions == 0
        assert result.next_dealing_date is not None

    @pytest.mark.asyncio
    async def test_queue_summary_without_terms(self) -> None:
        red_repo = AsyncMock()
        red_repo.count_by_state = AsyncMock(return_value={})
        red_repo.list_by_state = AsyncMock(return_value=[])

        terms_repo = AsyncMock()
        terms_repo.get_by_share_class = AsyncMock(return_value=None)

        service = _make_service(red_repo=red_repo, terms_repo=terms_repo)
        result = await service.get_queue_summary()

        assert result.pending_redemptions == 0
        assert result.next_dealing_date is None
