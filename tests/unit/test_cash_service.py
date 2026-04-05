"""Unit tests for CashManagementService — balance, settlement, and projection logic."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.cash_management.interface import CashFlowType
from app.modules.cash_management.service import CashManagementService
from app.shared.events import InProcessEventBus
from tests.helpers import EventCapture

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def event_bus() -> InProcessEventBus:
    return InProcessEventBus()


@pytest.fixture
def mock_session_factory() -> MagicMock:
    sf = MagicMock()
    scope_cm = AsyncMock()
    scope_cm.__aenter__ = AsyncMock(return_value=None)
    scope_cm.__aexit__ = AsyncMock(return_value=False)
    sf.fund_scope.return_value = scope_cm
    return sf


@pytest.fixture
def balance_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_portfolio.return_value = []
    repo.get_by_portfolio_currency.return_value = None
    return repo


@pytest.fixture
def journal_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def settlement_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def scheduled_flow_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def projection_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def security_master_service() -> AsyncMock:
    svc = AsyncMock()
    inst = MagicMock()
    inst.country = "US"
    svc.get_by_ticker.return_value = inst
    return svc


@pytest.fixture
def service(
    mock_session_factory,
    balance_repo,
    journal_repo,
    settlement_repo,
    scheduled_flow_repo,
    projection_repo,
    security_master_service,
    event_bus,
) -> CashManagementService:
    return CashManagementService(
        session_factory=mock_session_factory,
        balance_repo=balance_repo,
        journal_repo=journal_repo,
        settlement_repo=settlement_repo,
        scheduled_flow_repo=scheduled_flow_repo,
        projection_repo=projection_repo,
        security_master_service=security_master_service,
        event_bus=event_bus,
    )


# ---------------------------------------------------------------------------
# Credit / Debit
# ---------------------------------------------------------------------------


class TestCreditDebit:
    async def test_credit_updates_balance(self, service, balance_repo, journal_repo):
        pid = uuid4()
        await service.credit(
            pid, "USD", Decimal("50000"), CashFlowType.SUBSCRIPTION, description="Initial"
        )
        balance_repo.upsert.assert_called_once()
        journal_repo.insert.assert_called_once()
        # Verify the upserted balance
        record = balance_repo.upsert.call_args[0][0]
        assert record.available_balance == Decimal("50000")

    async def test_credit_adds_to_existing(self, service, balance_repo):
        pid = uuid4()
        existing = MagicMock()
        existing.available_balance = Decimal("100000")
        existing.pending_inflows = Decimal("0")
        existing.pending_outflows = Decimal("0")
        balance_repo.get_by_portfolio_currency.return_value = existing

        await service.credit(pid, "USD", Decimal("25000"), CashFlowType.SUBSCRIPTION)

        record = balance_repo.upsert.call_args[0][0]
        assert record.available_balance == Decimal("125000")

    async def test_debit_reduces_balance(self, service, balance_repo):
        pid = uuid4()
        existing = MagicMock()
        existing.available_balance = Decimal("100000")
        existing.pending_inflows = Decimal("0")
        existing.pending_outflows = Decimal("0")
        balance_repo.get_by_portfolio_currency.return_value = existing

        await service.debit(pid, "USD", Decimal("30000"), CashFlowType.REDEMPTION)

        record = balance_repo.upsert.call_args[0][0]
        assert record.available_balance == Decimal("70000")

    async def test_debit_from_zero_goes_negative(self, service, balance_repo):
        pid = uuid4()
        balance_repo.get_by_portfolio_currency.return_value = None

        await service.debit(pid, "USD", Decimal("10000"), CashFlowType.FEE)

        record = balance_repo.upsert.call_args[0][0]
        assert record.available_balance == Decimal("-10000")


# ---------------------------------------------------------------------------
# Create settlement
# ---------------------------------------------------------------------------


class TestCreateSettlement:
    async def test_creates_settlement_record(self, service, settlement_repo):
        pid = uuid4()
        await service.create_settlement(
            portfolio_id=pid,
            order_id=uuid4(),
            instrument_id="AAPL",
            currency="USD",
            amount=Decimal("-15000"),
            trade_date=date(2024, 1, 8),
            fund_slug="alpha",
        )
        settlement_repo.insert.assert_called_once()
        record = settlement_repo.insert.call_args[0][0]
        assert record.instrument_id == "AAPL"
        assert record.settlement_amount == Decimal("-15000")
        # US = T+1, Monday trade → Tuesday settlement
        assert record.settlement_date == date(2024, 1, 9)

    async def test_buy_updates_pending_outflows(self, service, balance_repo):
        pid = uuid4()
        await service.create_settlement(
            portfolio_id=pid,
            order_id=uuid4(),
            instrument_id="AAPL",
            currency="USD",
            amount=Decimal("-15000"),  # buy → negative
            trade_date=date(2024, 1, 8),
        )
        # Should update pending_outflows
        record = balance_repo.upsert.call_args[0][0]
        assert record.pending_outflows == Decimal("15000")

    async def test_sell_updates_pending_inflows(self, service, balance_repo):
        pid = uuid4()
        await service.create_settlement(
            portfolio_id=pid,
            order_id=uuid4(),
            instrument_id="AAPL",
            currency="USD",
            amount=Decimal("10000"),  # sell → positive
            trade_date=date(2024, 1, 8),
        )
        record = balance_repo.upsert.call_args[0][0]
        assert record.pending_inflows == Decimal("10000")

    async def test_settlement_publishes_event(self, service, event_bus):
        capture = EventCapture()
        capture.wire_to_bus(event_bus, ["fund-alpha.cash.settlement.created"])

        await service.create_settlement(
            portfolio_id=uuid4(),
            order_id=uuid4(),
            instrument_id="AAPL",
            currency="USD",
            amount=Decimal("-15000"),
            trade_date=date(2024, 1, 8),
            fund_slug="alpha",
        )

        events = capture.get_by_topic("cash.settlement.created")
        assert len(events) == 1

    async def test_settlement_uses_country_convention(
        self, service, security_master_service, settlement_repo
    ):
        """German instrument uses T+2 settlement."""
        inst = MagicMock()
        inst.country = "DE"
        security_master_service.get_by_ticker.return_value = inst

        await service.create_settlement(
            portfolio_id=uuid4(),
            order_id=uuid4(),
            instrument_id="SAP.DE",
            currency="EUR",
            amount=Decimal("-50000"),
            trade_date=date(2024, 1, 8),  # Monday
        )

        record = settlement_repo.insert.call_args[0][0]
        # T+2 from Monday → Wednesday
        assert record.settlement_date == date(2024, 1, 10)


# ---------------------------------------------------------------------------
# Get balances
# ---------------------------------------------------------------------------


class TestGetBalances:
    async def test_returns_empty_for_no_balances(self, service, balance_repo):
        balance_repo.get_by_portfolio.return_value = []
        result = await service.get_balances(uuid4())
        assert result == []

    async def test_total_balance_calculation(self, service, balance_repo):
        record = MagicMock()
        record.portfolio_id = uuid4()
        record.currency = "USD"
        record.available_balance = Decimal("100000")
        record.pending_inflows = Decimal("20000")
        record.pending_outflows = Decimal("5000")
        record.updated_at = MagicMock()
        balance_repo.get_by_portfolio.return_value = [record]

        result = await service.get_balances(uuid4())
        assert len(result) == 1
        # total = available + inflows - outflows = 115000
        assert result[0].total_balance == Decimal("115000")
