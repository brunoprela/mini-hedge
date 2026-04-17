"""Unit tests for CorporateActionsService — fetch_and_process orchestration, idempotency, events."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

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


def _make_position(quantity: Decimal = Decimal("100"), cost_basis: Decimal = Decimal("10000")) -> MagicMock:
    p = MagicMock()
    p.quantity = quantity
    p.cost_basis = cost_basis
    return p


def _make_existing_record(action_id: str = "CA-001") -> MagicMock:
    r = MagicMock()
    r.id = "00000000-0000-0000-0000-000000000099"
    r.action_id = action_id
    r.instrument_id = "AAPL"
    r.action_type = "dividend"
    r.ex_date = date(2026, 4, 1)
    r.status = "processed"
    r.processed_at = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
    r.error_message = None
    return r


def _stamp(record, **_kw):
    record.id = record.id or "00000000-0000-0000-0000-000000000099"
    record.processed_at = record.processed_at or datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
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
    repo.insert = AsyncMock(side_effect=_stamp)
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


# ------------------------------------------------------------------
# fetch_and_process
# ------------------------------------------------------------------


class TestFetchAndProcess:
    @pytest.mark.asyncio
    async def test_processes_dividend(self) -> None:
        action = _make_action("dividend", Decimal("2.00"))
        pos = _make_position(Decimal("100"), Decimal("10000"))
        svc, event_bus = _make_service(adapter_actions=[action], position=pos)

        results = await svc.fetch_and_process(_FUND, _PORTFOLIO, date(2026, 4, 1), date(2026, 4, 1))

        assert len(results) == 1
        assert results[0].status == ProcessingStatus.PROCESSED
        assert results[0].action_type == ActionType.DIVIDEND

    @pytest.mark.asyncio
    async def test_processes_stock_split(self) -> None:
        action = _make_action("stock_split", Decimal("2"), action_id="CA-002")
        pos = _make_position(Decimal("100"), Decimal("10000"))
        svc, event_bus = _make_service(adapter_actions=[action], position=pos)

        results = await svc.fetch_and_process(_FUND, _PORTFOLIO, date(2026, 4, 1), date(2026, 4, 1))

        assert len(results) == 1
        assert results[0].status == ProcessingStatus.PROCESSED

    @pytest.mark.asyncio
    async def test_skips_already_processed(self) -> None:
        action = _make_action("dividend")
        existing = _make_existing_record("CA-001")
        svc, event_bus = _make_service(adapter_actions=[action], existing_record=existing)

        results = await svc.fetch_and_process(_FUND, _PORTFOLIO, date(2026, 4, 1), date(2026, 4, 1))

        assert len(results) == 1
        # Should not insert again
        svc._repo.insert.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_unknown_action_type(self) -> None:
        action = _make_action("unknown_type")
        svc, event_bus = _make_service(adapter_actions=[action])

        # Service saves a FAILED record but _to_processed_action raises
        # because ActionType("unknown_type") is not valid.
        # This is a known edge case — the save succeeds but conversion fails.
        with pytest.raises(ValueError, match="unknown_type"):
            await svc.fetch_and_process(_FUND, _PORTFOLIO, date(2026, 4, 1), date(2026, 4, 1))

        # Verify the failed record was still persisted
        svc._repo.insert.assert_called_once()
        saved = svc._repo.insert.call_args.args[0]
        assert saved.status == ProcessingStatus.FAILED.value

    @pytest.mark.asyncio
    async def test_empty_when_no_actions(self) -> None:
        svc, _ = _make_service(adapter_actions=[])

        results = await svc.fetch_and_process(_FUND, _PORTFOLIO, date(2026, 4, 1), date(2026, 4, 1))

        assert results == []

    @pytest.mark.asyncio
    async def test_skips_zero_position_dividend(self) -> None:
        action = _make_action("dividend", Decimal("2.00"))
        svc, _ = _make_service(adapter_actions=[action], position=None)

        results = await svc.fetch_and_process(_FUND, _PORTFOLIO, date(2026, 4, 1), date(2026, 4, 1))

        # Dividend on zero position => no adjustments => SKIPPED
        assert results[0].status == ProcessingStatus.SKIPPED


# ------------------------------------------------------------------
# Event publishing
# ------------------------------------------------------------------


class TestCorporateActionsEvents:
    @pytest.mark.asyncio
    async def test_dividend_publishes_cash_event(self) -> None:
        action = _make_action("dividend", Decimal("2.00"))
        pos = _make_position(Decimal("100"), Decimal("10000"))
        svc, event_bus = _make_service(adapter_actions=[action], position=pos)

        await svc.fetch_and_process(_FUND, _PORTFOLIO, date(2026, 4, 1), date(2026, 4, 1))

        # Should publish: 1 cash event + 1 processed event = 2 total
        topics = [call.args[0] for call in event_bus.publish.call_args_list]
        event_types = [call.args[1].event_type for call in event_bus.publish.call_args_list]
        assert "corporate_action.dividend.cash" in event_types
        assert "corporate_actions.processed" in event_types

    @pytest.mark.asyncio
    async def test_split_publishes_trade_event(self) -> None:
        action = _make_action("stock_split", Decimal("2"), action_id="CA-003")
        pos = _make_position(Decimal("100"), Decimal("10000"))
        svc, event_bus = _make_service(adapter_actions=[action], position=pos)

        await svc.fetch_and_process(_FUND, _PORTFOLIO, date(2026, 4, 1), date(2026, 4, 1))

        event_types = [call.args[1].event_type for call in event_bus.publish.call_args_list]
        assert "corporate_action.stock_split" in event_types
        assert "corporate_actions.processed" in event_types

    @pytest.mark.asyncio
    async def test_processed_event_always_published(self) -> None:
        action = _make_action("dividend", Decimal("2.00"))
        pos = _make_position(Decimal("100"), Decimal("10000"))
        svc, event_bus = _make_service(adapter_actions=[action], position=pos)

        await svc.fetch_and_process(_FUND, _PORTFOLIO, date(2026, 4, 1), date(2026, 4, 1))

        processed_events = [
            c for c in event_bus.publish.call_args_list
            if c.args[1].event_type == "corporate_actions.processed"
        ]
        assert len(processed_events) == 1
        assert processed_events[0].args[1].data["action_id"] == "CA-001"


# ------------------------------------------------------------------
# list_processed
# ------------------------------------------------------------------


class TestListProcessed:
    @pytest.mark.asyncio
    async def test_returns_processed_actions(self) -> None:
        record = _make_existing_record()
        svc, _ = _make_service()
        svc._repo.list_all = AsyncMock(return_value=[record])

        results = await svc.list_processed()

        assert len(results) == 1
        assert results[0].action_id == "CA-001"

    @pytest.mark.asyncio
    async def test_empty_list(self) -> None:
        svc, _ = _make_service()
        assert await svc.list_processed() == []
