"""Extended tests for CorporateActionsService — covers exception handling paths
and additional event publishing scenarios."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.corporate_actions.interfaces import ActionType, ProcessingStatus
from app.modules.corporate_actions.services.corporate_actions import CorporateActionsService
from app.shared.adapters.corporate_actions import CorporateAction

_FUND = "alpha"
_PORTFOLIO = "00000000-0000-0000-0000-000000000001"


def _make_action(
    action_type: str = "dividend",
    amount: Decimal = Decimal("2.00"),
    instrument_id: str = "AAPL",
    action_id: str = "CA-001",
) -> CorporateAction:
    return CorporateAction(
        action_id=action_id,
        instrument_id=instrument_id,
        action_type=action_type,
        ex_date=date(2026, 4, 1),
        amount=amount,
    )


def _make_position(
    quantity: Decimal = Decimal("100"), cost_basis: Decimal = Decimal("10000")
) -> MagicMock:
    p = MagicMock()
    p.quantity = quantity
    p.cost_basis = cost_basis
    return p


def _stamp(record, **_kw):
    record.id = record.id or "00000000-0000-0000-0000-000000000099"
    record.processed_at = record.processed_at or datetime(
        2026, 4, 1, 12, 0, tzinfo=timezone.utc
    )
    return record


def _make_service(
    *,
    adapter_actions: list | None = None,
    existing_record: MagicMock | None = None,
    position: MagicMock | None = None,
) -> tuple[CorporateActionsService, AsyncMock]:
    sf = MagicMock()
    repo = AsyncMock()
    repo.get_by_action_id = AsyncMock(return_value=existing_record)
    repo.save = AsyncMock(side_effect=_stamp)
    repo.list_all = AsyncMock(return_value=[])

    adapter = AsyncMock()
    adapter.get_actions = AsyncMock(return_value=adapter_actions or [])

    event_bus = AsyncMock()

    position_service = AsyncMock()
    position_service.get_position = AsyncMock(return_value=position)

    svc = CorporateActionsService(
        session_factory=sf,
        repo=repo,
        corporate_actions_adapter=adapter,
        event_bus=event_bus,
        position_service=position_service,
    )
    return svc, event_bus


# ---------------------------------------------------------------------------
# compute_adjustments exception path (service lines 142-159)
# ---------------------------------------------------------------------------


class TestProcessingExceptionPath:
    @pytest.mark.asyncio
    async def test_compute_adjustments_exception_saves_failed_record(self) -> None:
        """When compute_adjustments raises, service saves a FAILED record."""
        action = _make_action("dividend", Decimal("2.00"), action_id="CA-ERR")
        pos = _make_position(Decimal("100"), Decimal("10000"))
        svc, event_bus = _make_service(adapter_actions=[action], position=pos)

        with patch(
            "app.modules.corporate_actions.services.corporate_actions.compute_adjustments",
            side_effect=RuntimeError("boom"),
        ):
            # _to_processed_action will work since action_type is valid
            results = await svc.fetch_and_process(
                _FUND, _PORTFOLIO, date(2026, 4, 1), date(2026, 4, 1)
            )

        assert len(results) == 1
        assert results[0].status == ProcessingStatus.FAILED

        # Verify the failed record was persisted
        svc._repo.save.assert_called_once()
        saved_record = svc._repo.save.call_args.args[0]
        assert saved_record.status == ProcessingStatus.FAILED.value
        assert saved_record.error_message == "boom"


# ---------------------------------------------------------------------------
# Merger event publishing (trade + cash events)
# ---------------------------------------------------------------------------


class TestMergerEventPublishing:
    @pytest.mark.asyncio
    async def test_merger_publishes_trade_and_cash_events(self) -> None:
        """Merger with cash consideration publishes both trade (sell) and cash events."""
        action = _make_action(
            "merger", Decimal("150.00"), action_id="CA-MERGER-001"
        )
        pos = _make_position(Decimal("100"), Decimal("10000"))
        svc, event_bus = _make_service(adapter_actions=[action], position=pos)

        results = await svc.fetch_and_process(
            _FUND, _PORTFOLIO, date(2026, 4, 1), date(2026, 4, 1)
        )

        assert len(results) == 1
        assert results[0].status == ProcessingStatus.PROCESSED

        event_types = [
            call.args[1].event_type for call in event_bus.publish.call_args_list
        ]
        # Merger produces: trade event (sell) + cash event + processed event
        assert "corporate_action.merger" in event_types
        assert "corporate_action.merger.cash" in event_types
        assert "corporate_actions.processed" in event_types


class TestReverseSplitEventPublishing:
    @pytest.mark.asyncio
    async def test_reverse_split_publishes_sell_event(self) -> None:
        """Reverse split publishes a sell trade event (quantity decreases)."""
        action = _make_action(
            "reverse_split", Decimal("3"), action_id="CA-RSPLIT-001"
        )
        pos = _make_position(Decimal("300"), Decimal("30000"))
        svc, event_bus = _make_service(adapter_actions=[action], position=pos)

        results = await svc.fetch_and_process(
            _FUND, _PORTFOLIO, date(2026, 4, 1), date(2026, 4, 1)
        )

        assert len(results) == 1
        assert results[0].status == ProcessingStatus.PROCESSED

        event_types = [
            call.args[1].event_type for call in event_bus.publish.call_args_list
        ]
        assert "corporate_action.reverse_split" in event_types


class TestSpinoffEventPublishing:
    @pytest.mark.asyncio
    async def test_spinoff_publishes_trade_event_for_child(self) -> None:
        """Spinoff publishes a buy trade event for the child instrument."""
        action = _make_action(
            "spinoff", Decimal("0.20"), action_id="CA-SPINOFF-001"
        )
        pos = _make_position(Decimal("100"), Decimal("10000"))
        svc, event_bus = _make_service(adapter_actions=[action], position=pos)

        results = await svc.fetch_and_process(
            _FUND, _PORTFOLIO, date(2026, 4, 1), date(2026, 4, 1)
        )

        assert len(results) == 1
        assert results[0].status == ProcessingStatus.PROCESSED

        event_types = [
            call.args[1].event_type for call in event_bus.publish.call_args_list
        ]
        # Spinoff: child gets quantity_delta > 0 -> buy event
        assert "corporate_action.spinoff" in event_types
