"""Extended tests for SubscriptionService — covers not-found paths, get/list methods."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from app.modules.investor_operations.interfaces import SubscriptionState
from app.modules.investor_operations.services.subscription import SubscriptionService

_REQ_ID = "00000000-0000-0000-0000-000000000001"
_INV_ID = "00000000-0000-0000-0000-000000000010"


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


def _make_service(
    *,
    sub_repo: AsyncMock | None = None,
    terms_repo: AsyncMock | None = None,
) -> SubscriptionService:
    _sub_repo = sub_repo or AsyncMock()
    _terms_repo = terms_repo or AsyncMock()
    _terms_repo.get_by_share_class = getattr(
        _terms_repo, "get_by_share_class", AsyncMock(return_value=None)
    )
    return SubscriptionService(
        subscription_repo=_sub_repo,
        fund_terms_repo=_terms_repo,
        kyc_repo=AsyncMock(),
        capital_service=AsyncMock(),
        event_bus=AsyncMock(),
    )


class TestOpsReviewNotFound:
    """Covers lines 168-169."""

    @pytest.mark.asyncio
    async def test_not_found_raises(self) -> None:
        sub_repo = AsyncMock()
        sub_repo.get_by_id = AsyncMock(return_value=None)

        service = _make_service(sub_repo=sub_repo)
        with pytest.raises(ValueError, match="not found"):
            await service.ops_review(_REQ_ID, approved=True, decision_by="ops-1")


class TestGpDecisionNotFound:
    """Covers lines 219-220."""

    @pytest.mark.asyncio
    async def test_not_found_raises(self) -> None:
        sub_repo = AsyncMock()
        sub_repo.get_by_id = AsyncMock(return_value=None)

        service = _make_service(sub_repo=sub_repo)
        with pytest.raises(ValueError, match="not found"):
            await service.gp_decision(_REQ_ID, approved=True, decision_by="gp-1")


class TestConfirmWireNotFound:
    """Covers lines 270-271."""

    @pytest.mark.asyncio
    async def test_not_found_raises(self) -> None:
        sub_repo = AsyncMock()
        sub_repo.get_by_id = AsyncMock(return_value=None)

        service = _make_service(sub_repo=sub_repo)
        with pytest.raises(ValueError, match="not found"):
            await service.confirm_wire(_REQ_ID, wire_reference="WIRE-X")


class TestGetSubscription:
    """Covers lines 417-418."""

    @pytest.mark.asyncio
    async def test_returns_summary_when_found(self) -> None:
        record = _make_sub_record()
        sub_repo = AsyncMock()
        sub_repo.get_by_id = AsyncMock(return_value=record)

        service = _make_service(sub_repo=sub_repo)
        result = await service.get_subscription(_REQ_ID)

        assert result is not None
        assert result.requested_amount == Decimal("500000")

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        sub_repo = AsyncMock()
        sub_repo.get_by_id = AsyncMock(return_value=None)

        service = _make_service(sub_repo=sub_repo)
        result = await service.get_subscription(_REQ_ID)

        assert result is None


class TestListSubscriptions:
    """Covers lines 427-445: by state, by investor, default all-pending paths."""

    @pytest.mark.asyncio
    async def test_list_by_state(self) -> None:
        records = [_make_sub_record(), _make_sub_record(id="00000000-0000-0000-0000-000000000099")]
        sub_repo = AsyncMock()
        sub_repo.list_by_state = AsyncMock(return_value=records)

        service = _make_service(sub_repo=sub_repo)
        result = await service.list_subscriptions(state="pending_kyc")

        assert len(result) == 2
        sub_repo.list_by_state.assert_called_once_with("pending_kyc", session=None)

    @pytest.mark.asyncio
    async def test_list_by_investor(self) -> None:
        records = [_make_sub_record()]
        sub_repo = AsyncMock()
        sub_repo.list_by_investor = AsyncMock(return_value=records)

        service = _make_service(sub_repo=sub_repo)
        result = await service.list_subscriptions(investor_id=_INV_ID)

        assert len(result) == 1
        sub_repo.list_by_investor.assert_called_once_with(_INV_ID, session=None)

    @pytest.mark.asyncio
    async def test_list_default_all_pending_states(self) -> None:
        sub_repo = AsyncMock()
        sub_repo.list_by_state = AsyncMock(return_value=[])

        service = _make_service(sub_repo=sub_repo)
        result = await service.list_subscriptions()

        assert result == []
        # Should query for each pending state: 8 states
        assert sub_repo.list_by_state.call_count == 8
