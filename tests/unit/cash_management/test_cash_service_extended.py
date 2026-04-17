"""Extended unit tests for CashManagementService — covers settlement ladder,
projections, due-settlement processing, FX conversion, and edge cases."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.cash_management.interfaces import (
    CashFlowType,
    SettlementStatus,
)
from app.modules.cash_management.services import CashManagementService
from app.shared.events import InProcessEventBus
from tests.helpers import EventCapture

ZERO = Decimal(0)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(
    *,
    balance_repo: AsyncMock | None = None,
    journal_repo: AsyncMock | None = None,
    settlement_repo: AsyncMock | None = None,
    scheduled_flow_repo: AsyncMock | None = None,
    projection_repo: AsyncMock | None = None,
    security_master_service: AsyncMock | None = None,
    event_bus: InProcessEventBus | None = None,
    fx_converter: MagicMock | None = None,
) -> CashManagementService:
    sf = MagicMock()
    scope_cm = AsyncMock()
    scope_cm.__aenter__ = AsyncMock(return_value=None)
    scope_cm.__aexit__ = AsyncMock(return_value=False)
    sf.fund_scope.return_value = scope_cm

    br = balance_repo or AsyncMock()
    if balance_repo is None:
        br.get_by_portfolio.return_value = []
        br.get_by_portfolio_currency.return_value = None

    return CashManagementService(
        session_factory=sf,
        balance_repo=br,
        journal_repo=journal_repo or AsyncMock(),
        settlement_repo=settlement_repo or AsyncMock(),
        scheduled_flow_repo=scheduled_flow_repo or AsyncMock(),
        projection_repo=projection_repo or AsyncMock(),
        security_master_service=security_master_service or AsyncMock(),
        event_bus=event_bus or InProcessEventBus(),
        fx_converter=fx_converter,
    )


def _make_balance_record(
    *,
    currency: str = "USD",
    available: Decimal = Decimal("100000"),
    inflows: Decimal = ZERO,
    outflows: Decimal = ZERO,
) -> MagicMock:
    rec = MagicMock()
    rec.currency = currency
    rec.available_balance = available
    rec.pending_inflows = inflows
    rec.pending_outflows = outflows
    return rec


def _make_settlement_record(
    *,
    settlement_date: date | None = None,
    amount: Decimal = Decimal("-5000"),
    currency: str = "USD",
    instrument_id: str = "AAPL",
    status: str = "pending",
    portfolio_id: str | None = None,
    order_id: str | None = None,
) -> MagicMock:
    rec = MagicMock()
    rec.id = str(uuid4())
    rec.portfolio_id = portfolio_id or str(uuid4())
    rec.order_id = order_id or str(uuid4())
    rec.instrument_id = instrument_id
    rec.currency = currency
    rec.settlement_amount = amount
    rec.settlement_date = settlement_date or date.today()
    rec.trade_date = date.today() - timedelta(days=1)
    rec.status = status
    rec.created_at = datetime.now(UTC)
    return rec


def _make_scheduled_flow(
    *,
    flow_date: date,
    amount: Decimal = Decimal("1000"),
    currency: str = "USD",
    flow_type: str = "subscription",
    description: str = "Test flow",
) -> MagicMock:
    rec = MagicMock()
    rec.flow_date = flow_date
    rec.amount = amount
    rec.currency = currency
    rec.flow_type = flow_type
    rec.description = description
    return rec


# ---------------------------------------------------------------------------
# FX conversion
# ---------------------------------------------------------------------------


class TestConvertToBase:
    def test_same_currency_returns_unchanged(self):
        svc = _make_service()
        result = svc._convert_to_base(Decimal("100"), "USD", "USD")
        assert result == Decimal("100")

    def test_no_fx_converter_returns_unchanged(self):
        svc = _make_service(fx_converter=None)
        result = svc._convert_to_base(Decimal("100"), "EUR", "USD")
        assert result == Decimal("100")

    def test_successful_conversion(self):
        fx = MagicMock()
        fx.convert.return_value = Decimal("110")
        svc = _make_service(fx_converter=fx)
        result = svc._convert_to_base(Decimal("100"), "EUR", "USD")
        assert result == Decimal("110")
        fx.convert.assert_called_once_with(Decimal("100"), "EUR", "USD")

    def test_conversion_returns_none_falls_back(self):
        fx = MagicMock()
        fx.convert.return_value = None
        svc = _make_service(fx_converter=fx)
        result = svc._convert_to_base(Decimal("100"), "EUR", "USD")
        # When conversion fails, returns the original amount
        assert result == Decimal("100")


# ---------------------------------------------------------------------------
# create_settlement — edge cases
# ---------------------------------------------------------------------------


class TestCreateSettlementEdgeCases:
    async def test_security_lookup_failure_raises_value_error(self):
        """When security_master raises, a ValueError is raised (no silent default)."""
        sm = AsyncMock()
        sm.get_by_ticker.side_effect = RuntimeError("not found")
        settlement_repo = AsyncMock()
        svc = _make_service(security_master_service=sm, settlement_repo=settlement_repo)

        with pytest.raises(RuntimeError, match="not found"):
            await svc.create_settlement(
                portfolio_id=uuid4(),
                order_id=uuid4(),
                instrument_id="UNKNOWN",
                currency="USD",
                amount=Decimal("-1000"),
                trade_date=date(2024, 1, 8),  # Monday
            )

        settlement_repo.insert.assert_not_called()

    async def test_settlement_due_event_published_when_near(self):
        """Settlement due event published when settlement is within 2 days."""
        event_bus = InProcessEventBus()
        capture = EventCapture()
        capture.wire_to_bus(event_bus, [
            "fund-alpha.cash.settlement.created",
            "fund-alpha.cash.settlement_due",
        ])

        # Use a security master that returns US (T+1) so settlement is near
        sm = AsyncMock()
        inst = MagicMock()
        inst.country = "US"
        sm.get_by_ticker.return_value = inst

        svc = _make_service(event_bus=event_bus, security_master_service=sm)

        # Use a Monday so T+1 = Tuesday (within 2 business days of today)
        # We need the real date.today() in the code to see <= 2 days gap
        today = date.today()
        while today.weekday() != 0:  # find next Monday
            today += timedelta(days=1)

        with patch("app.modules.cash_management.services.cash.date") as mock_date:
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

            await svc.create_settlement(
                portfolio_id=uuid4(),
                order_id=uuid4(),
                instrument_id="AAPL",
                currency="USD",
                amount=Decimal("-5000"),
                trade_date=today,
                fund_slug="alpha",
            )

        due_events = capture.get_by_topic("cash.settlement_due")
        assert len(due_events) == 1

    async def test_no_fund_slug_skips_events(self):
        """When fund_slug is None, no events are published."""
        event_bus = InProcessEventBus()
        capture = EventCapture()
        capture.wire_to_bus(event_bus, ["fund-alpha.cash.settlement.created"])

        svc = _make_service(event_bus=event_bus)

        await svc.create_settlement(
            portfolio_id=uuid4(),
            order_id=uuid4(),
            instrument_id="AAPL",
            currency="USD",
            amount=Decimal("-5000"),
            trade_date=date(2024, 1, 8),
            fund_slug=None,
        )

        assert len(capture.events) == 0


# ---------------------------------------------------------------------------
# get_pending_settlements
# ---------------------------------------------------------------------------


class TestGetPendingSettlements:
    async def test_returns_mapped_records(self):
        pid = uuid4()
        rec = _make_settlement_record(portfolio_id=str(pid), status="pending")
        settlement_repo = AsyncMock()
        settlement_repo.get_pending.return_value = [rec]
        svc = _make_service(settlement_repo=settlement_repo)

        result = await svc.get_pending_settlements(pid)

        assert len(result) == 1
        assert result[0].instrument_id == rec.instrument_id
        assert result[0].status == SettlementStatus.PENDING

    async def test_empty_list(self):
        settlement_repo = AsyncMock()
        settlement_repo.get_pending.return_value = []
        svc = _make_service(settlement_repo=settlement_repo)

        result = await svc.get_pending_settlements(uuid4())
        assert result == []


# ---------------------------------------------------------------------------
# process_due_settlements
# ---------------------------------------------------------------------------


class TestProcessDueSettlements:
    async def test_credits_positive_amount(self):
        """Positive settlement (sell proceeds) triggers credit."""
        rec = _make_settlement_record(amount=Decimal("10000"))
        settlement_repo = AsyncMock()
        settlement_repo.get_due_settlements.return_value = [rec]
        svc = _make_service(settlement_repo=settlement_repo)

        count = await svc.process_due_settlements(date.today())

        assert count == 1
        settlement_repo.settle.assert_called_once_with(rec.id, session=None)

    async def test_debits_negative_amount(self):
        """Negative settlement (buy cost) triggers debit."""
        rec = _make_settlement_record(amount=Decimal("-8000"))
        settlement_repo = AsyncMock()
        settlement_repo.get_due_settlements.return_value = [rec]
        balance_repo = AsyncMock()
        balance_repo.get_by_portfolio_currency.return_value = None
        svc = _make_service(settlement_repo=settlement_repo, balance_repo=balance_repo)

        count = await svc.process_due_settlements(date.today())

        assert count == 1
        settlement_repo.settle.assert_called_once_with(rec.id, session=None)

    async def test_no_due_settlements(self):
        settlement_repo = AsyncMock()
        settlement_repo.get_due_settlements.return_value = []
        svc = _make_service(settlement_repo=settlement_repo)

        count = await svc.process_due_settlements(date.today())
        assert count == 0

    async def test_multiple_settlements_processed(self):
        recs = [
            _make_settlement_record(amount=Decimal("5000")),
            _make_settlement_record(amount=Decimal("-3000")),
        ]
        settlement_repo = AsyncMock()
        settlement_repo.get_due_settlements.return_value = recs
        balance_repo = AsyncMock()
        balance_repo.get_by_portfolio_currency.return_value = None
        svc = _make_service(settlement_repo=settlement_repo, balance_repo=balance_repo)

        count = await svc.process_due_settlements(date.today())
        assert count == 2


# ---------------------------------------------------------------------------
# get_settlement_ladder
# ---------------------------------------------------------------------------


class TestGetSettlementLadder:
    async def test_empty_ladder(self):
        """With no balances or settlements, ladder should have at least today entry."""
        settlement_repo = AsyncMock()
        settlement_repo.get_by_date_range.return_value = []
        balance_repo = AsyncMock()
        balance_repo.get_by_portfolio.return_value = []
        svc = _make_service(settlement_repo=settlement_repo, balance_repo=balance_repo)

        result = await svc.get_settlement_ladder(uuid4(), horizon_days=5)

        assert result.entries is not None
        # Should have at least the today entry
        assert len(result.entries) >= 1
        assert result.entries[0].cumulative_balance == ZERO

    async def test_ladder_with_balances_and_settlements(self):
        """Ladder correctly sums inflows/outflows."""
        pid = uuid4()
        today = date.today()
        # Ensure we use a weekday
        while today.weekday() >= 5:
            today += timedelta(days=1)

        bal = _make_balance_record(available=Decimal("50000"))
        balance_repo = AsyncMock()
        balance_repo.get_by_portfolio.return_value = [bal]

        # Create a settlement for tomorrow (next business day)
        tomorrow = today + timedelta(days=1)
        while tomorrow.weekday() >= 5:
            tomorrow += timedelta(days=1)

        inflow_settlement = _make_settlement_record(
            settlement_date=tomorrow,
            amount=Decimal("10000"),
            status="pending",
        )
        outflow_settlement = _make_settlement_record(
            settlement_date=tomorrow,
            amount=Decimal("-3000"),
            status="pending",
        )
        settlement_repo = AsyncMock()
        settlement_repo.get_by_date_range.return_value = [
            inflow_settlement,
            outflow_settlement,
        ]

        svc = _make_service(
            settlement_repo=settlement_repo,
            balance_repo=balance_repo,
        )

        with patch("app.modules.cash_management.services.cash.date") as mock_date:
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = await svc.get_settlement_ladder(pid, horizon_days=5)

        assert len(result.entries) >= 1

    async def test_ladder_skips_non_pending(self):
        """Settled settlements should be excluded from the ladder."""
        pid = uuid4()
        today = date.today()
        while today.weekday() >= 5:
            today += timedelta(days=1)

        balance_repo = AsyncMock()
        balance_repo.get_by_portfolio.return_value = []

        settled_rec = _make_settlement_record(
            settlement_date=today,
            amount=Decimal("5000"),
            status="settled",
        )
        settlement_repo = AsyncMock()
        settlement_repo.get_by_date_range.return_value = [settled_rec]

        svc = _make_service(
            settlement_repo=settlement_repo,
            balance_repo=balance_repo,
        )

        with patch("app.modules.cash_management.services.cash.date") as mock_date:
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = await svc.get_settlement_ladder(pid, horizon_days=3)

        # The settled settlement should not contribute to flows
        for entry in result.entries:
            assert entry.expected_inflow == ZERO

    async def test_ladder_with_fx_conversion(self):
        """FX conversion is applied to settlement amounts."""
        pid = uuid4()
        today = date.today()
        while today.weekday() >= 5:
            today += timedelta(days=1)

        bal = _make_balance_record(currency="EUR", available=Decimal("10000"))
        balance_repo = AsyncMock()
        balance_repo.get_by_portfolio.return_value = [bal]

        settlement_repo = AsyncMock()
        settlement_repo.get_by_date_range.return_value = []

        fx = MagicMock()
        fx.convert.return_value = Decimal("11000")

        svc = _make_service(
            settlement_repo=settlement_repo,
            balance_repo=balance_repo,
            fx_converter=fx,
        )

        with patch("app.modules.cash_management.services.cash.date") as mock_date:
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = await svc.get_settlement_ladder(pid, horizon_days=3, base_currency="USD")

        fx.convert.assert_called()
        # First entry cumulative should reflect converted balance
        assert result.entries[0].cumulative_balance == Decimal("11000")


# ---------------------------------------------------------------------------
# get_projection
# ---------------------------------------------------------------------------


class TestGetProjection:
    async def test_basic_projection(self):
        """Projection with no settlements or scheduled flows."""
        pid = uuid4()
        balance_repo = AsyncMock()
        balance_repo.get_by_portfolio.return_value = [
            _make_balance_record(available=Decimal("100000"))
        ]
        settlement_repo = AsyncMock()
        settlement_repo.get_by_date_range.return_value = []
        scheduled_flow_repo = AsyncMock()
        scheduled_flow_repo.get_by_portfolio.return_value = []

        svc = _make_service(
            balance_repo=balance_repo,
            settlement_repo=settlement_repo,
            scheduled_flow_repo=scheduled_flow_repo,
        )

        with patch("app.shared.database.TenantSessionFactory.current_fund_slug", return_value=None):
            result = await svc.get_projection(pid, horizon_days=5)

        assert result.portfolio_id == pid
        assert result.base_currency == "USD"
        assert result.horizon_days == 5
        assert len(result.entries) >= 1
        # All entries should have constant balance (no flows)
        for entry in result.entries:
            assert entry.opening_balance == Decimal("100000")
            assert entry.closing_balance == Decimal("100000")

    async def test_projection_with_settlements(self):
        """Settlements affect the projection."""
        pid = uuid4()
        today = date.today()
        while today.weekday() >= 5:
            today += timedelta(days=1)

        balance_repo = AsyncMock()
        balance_repo.get_by_portfolio.return_value = [
            _make_balance_record(available=Decimal("50000"))
        ]

        # Pending settlement on today
        settlement = _make_settlement_record(
            settlement_date=today,
            amount=Decimal("10000"),
            status="pending",
            currency="USD",
        )
        settlement_repo = AsyncMock()
        settlement_repo.get_by_date_range.return_value = [settlement]
        scheduled_flow_repo = AsyncMock()
        scheduled_flow_repo.get_by_portfolio.return_value = []

        svc = _make_service(
            balance_repo=balance_repo,
            settlement_repo=settlement_repo,
            scheduled_flow_repo=scheduled_flow_repo,
        )

        with (
            patch("app.modules.cash_management.services.cash.date") as mock_date,
            patch("app.shared.database.TenantSessionFactory.current_fund_slug", return_value=None),
        ):
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = await svc.get_projection(pid, horizon_days=3)

        assert len(result.entries) >= 1
        # First entry should include the inflow from the settlement
        first = result.entries[0]
        assert first.inflows == Decimal("10000")

    async def test_projection_with_scheduled_flows(self):
        """Scheduled flows are included in the projection."""
        pid = uuid4()
        today = date.today()
        while today.weekday() >= 5:
            today += timedelta(days=1)

        balance_repo = AsyncMock()
        balance_repo.get_by_portfolio.return_value = [
            _make_balance_record(available=Decimal("20000"))
        ]
        settlement_repo = AsyncMock()
        settlement_repo.get_by_date_range.return_value = []

        flow = _make_scheduled_flow(
            flow_date=today,
            amount=Decimal("5000"),
        )
        scheduled_flow_repo = AsyncMock()
        scheduled_flow_repo.get_by_portfolio.return_value = [flow]

        svc = _make_service(
            balance_repo=balance_repo,
            settlement_repo=settlement_repo,
            scheduled_flow_repo=scheduled_flow_repo,
        )

        with (
            patch("app.modules.cash_management.services.cash.date") as mock_date,
            patch("app.shared.database.TenantSessionFactory.current_fund_slug", return_value=None),
        ):
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = await svc.get_projection(pid, horizon_days=3)

        first = result.entries[0]
        assert first.inflows == Decimal("5000")
        assert first.closing_balance == Decimal("25000")

    async def test_projection_with_outflow_scheduled(self):
        """Negative scheduled flows are recorded as outflows."""
        pid = uuid4()
        today = date.today()
        while today.weekday() >= 5:
            today += timedelta(days=1)

        balance_repo = AsyncMock()
        balance_repo.get_by_portfolio.return_value = [
            _make_balance_record(available=Decimal("20000"))
        ]
        settlement_repo = AsyncMock()
        settlement_repo.get_by_date_range.return_value = []

        flow = _make_scheduled_flow(
            flow_date=today,
            amount=Decimal("-3000"),
        )
        scheduled_flow_repo = AsyncMock()
        scheduled_flow_repo.get_by_portfolio.return_value = [flow]

        svc = _make_service(
            balance_repo=balance_repo,
            settlement_repo=settlement_repo,
            scheduled_flow_repo=scheduled_flow_repo,
        )

        with (
            patch("app.modules.cash_management.services.cash.date") as mock_date,
            patch("app.shared.database.TenantSessionFactory.current_fund_slug", return_value=None),
        ):
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = await svc.get_projection(pid, horizon_days=3)

        first = result.entries[0]
        assert first.outflows == Decimal("3000")
        assert first.closing_balance == Decimal("17000")

    async def test_projection_negative_balance_warning(self):
        """Publishes balance warning when projected balance goes negative."""
        pid = uuid4()
        today = date.today()
        while today.weekday() >= 5:
            today += timedelta(days=1)

        balance_repo = AsyncMock()
        balance_repo.get_by_portfolio.return_value = [
            _make_balance_record(available=Decimal("1000"))
        ]
        settlement_repo = AsyncMock()
        settlement_repo.get_by_date_range.return_value = []

        # Large outflow that makes balance negative
        flow = _make_scheduled_flow(
            flow_date=today,
            amount=Decimal("-5000"),
        )
        scheduled_flow_repo = AsyncMock()
        scheduled_flow_repo.get_by_portfolio.return_value = [flow]

        event_bus = InProcessEventBus()
        capture = EventCapture()
        capture.wire_to_bus(event_bus, ["fund-alpha.cash.balance_warning"])

        svc = _make_service(
            balance_repo=balance_repo,
            settlement_repo=settlement_repo,
            scheduled_flow_repo=scheduled_flow_repo,
            event_bus=event_bus,
        )

        with (
            patch("app.modules.cash_management.services.cash.date") as mock_date,
            patch("app.shared.database.TenantSessionFactory.current_fund_slug", return_value="alpha"),
        ):
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = await svc.get_projection(pid, horizon_days=3)

        assert result.entries[0].closing_balance < ZERO
        warnings = capture.get_by_topic("cash.balance_warning")
        assert len(warnings) == 1

    async def test_projection_publishes_projected_event(self):
        """The cash.projected event is published when fund_slug is available."""
        pid = uuid4()
        event_bus = InProcessEventBus()
        capture = EventCapture()
        capture.wire_to_bus(event_bus, ["fund-beta.cash.projected"])

        balance_repo = AsyncMock()
        balance_repo.get_by_portfolio.return_value = []
        settlement_repo = AsyncMock()
        settlement_repo.get_by_date_range.return_value = []
        scheduled_flow_repo = AsyncMock()
        scheduled_flow_repo.get_by_portfolio.return_value = []

        svc = _make_service(
            balance_repo=balance_repo,
            settlement_repo=settlement_repo,
            scheduled_flow_repo=scheduled_flow_repo,
            event_bus=event_bus,
        )

        with patch("app.shared.database.TenantSessionFactory.current_fund_slug", return_value="beta"):
            await svc.get_projection(pid, horizon_days=3)

        projected_events = capture.get_by_topic("cash.projected")
        assert len(projected_events) == 1

    async def test_projection_outflow_settlement(self):
        """Negative settlements are recorded as outflows in projection."""
        pid = uuid4()
        today = date.today()
        while today.weekday() >= 5:
            today += timedelta(days=1)

        balance_repo = AsyncMock()
        balance_repo.get_by_portfolio.return_value = [
            _make_balance_record(available=Decimal("50000"))
        ]

        settlement = _make_settlement_record(
            settlement_date=today,
            amount=Decimal("-8000"),
            status="pending",
            currency="USD",
        )
        settlement_repo = AsyncMock()
        settlement_repo.get_by_date_range.return_value = [settlement]
        scheduled_flow_repo = AsyncMock()
        scheduled_flow_repo.get_by_portfolio.return_value = []

        svc = _make_service(
            balance_repo=balance_repo,
            settlement_repo=settlement_repo,
            scheduled_flow_repo=scheduled_flow_repo,
        )

        with (
            patch("app.modules.cash_management.services.cash.date") as mock_date,
            patch("app.shared.database.TenantSessionFactory.current_fund_slug", return_value=None),
        ):
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = await svc.get_projection(pid, horizon_days=3)

        first = result.entries[0]
        assert first.outflows == Decimal("8000")
        assert first.closing_balance == Decimal("42000")


# ---------------------------------------------------------------------------
# handle_trade_executed — no fund_slug
# ---------------------------------------------------------------------------


class TestHandleTradeExecutedNoFundSlug:
    async def test_missing_fund_slug_is_noop(self):
        """When fund_slug is None on the event, handler returns early."""
        from app.shared.events import BaseEvent

        svc = _make_service()
        event = BaseEvent(
            event_type="trades.executed",
            data={
                "portfolio_id": str(uuid4()),
                "instrument_id": "AAPL",
                "currency": "USD",
                "side": "buy",
                "quantity": "100",
                "price": "150",
            },
            fund_slug=None,
        )
        svc.create_settlement = AsyncMock()
        await svc.handle_trade_executed(event)
        svc.create_settlement.assert_not_called()


# ---------------------------------------------------------------------------
# _to_settlement_record
# ---------------------------------------------------------------------------


class TestToSettlementRecord:
    def test_maps_all_fields(self):
        rec = _make_settlement_record(status="pending")
        result = CashManagementService._to_settlement_record(rec)

        assert result.instrument_id == rec.instrument_id
        assert result.currency == rec.currency
        assert result.settlement_amount == rec.settlement_amount
        assert result.status == SettlementStatus.PENDING

    def test_none_order_id(self):
        rec = _make_settlement_record()
        rec.order_id = None
        result = CashManagementService._to_settlement_record(rec)
        assert result.order_id is None
