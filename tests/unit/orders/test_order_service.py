"""Unit tests for OrderService — mocked repos, real event bus."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.modules.compliance.interfaces import (
    ComplianceDecision,
    EvaluationResult,
    Severity,
)
from app.modules.orders.core.state_machine import InvalidTransitionError
from app.modules.orders.interfaces import OrderState
from app.modules.orders.models.order import OrderRecord
from app.modules.orders.services import OrderService
from app.shared.events import InProcessEventBus
from tests.factories import make_order_request
from tests.helpers import EventCapture, StubBroker

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NOW = datetime.now(UTC)


def _make_order_record(**overrides) -> OrderRecord:
    """Build a minimal OrderRecord for mock returns."""
    defaults = dict(
        id=str(uuid4()),
        portfolio_id=str(uuid4()),
        instrument_id="AAPL",
        side="buy",
        order_type="market",
        quantity=Decimal("100"),
        filled_quantity=Decimal("0"),
        limit_price=Decimal("150.00"),
        stop_price=None,
        avg_fill_price=None,
        state=OrderState.DRAFT.value,
        rejection_reason=None,
        compliance_results=None,
        time_in_force="day",
        fund_slug="alpha",
        parent_order_id=None,
        algo_type=None,
        algo_params=None,
        is_parent=False,
        broker_id=None,
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    record = MagicMock(spec=OrderRecord)
    for k, v in defaults.items():
        setattr(record, k, v)
    return record


def _approved_decision() -> ComplianceDecision:
    return ComplianceDecision(
        approved=True,
        results=[
            EvaluationResult(
                rule_id=uuid4(),
                rule_name="concentration",
                passed=True,
                severity=Severity.BLOCK,
                message="OK",
            )
        ],
        blocked_by=[],
    )


def _rejected_decision() -> ComplianceDecision:
    return ComplianceDecision(
        approved=False,
        results=[
            EvaluationResult(
                rule_id=uuid4(),
                rule_name="concentration",
                passed=False,
                severity=Severity.BLOCK,
                message="Too concentrated",
            )
        ],
        blocked_by=["concentration"],
    )


@pytest.fixture
def event_bus() -> InProcessEventBus:
    return InProcessEventBus()


@pytest.fixture
def capture(event_bus: InProcessEventBus) -> EventCapture:
    cap = EventCapture()
    cap.wire_to_bus(
        event_bus,
        [
            "fund-alpha.trades.executed",
            "fund-alpha.trades.approved",
            "fund-alpha.trades.rejected",
            "fund-alpha.orders.created",
            "fund-alpha.orders.filled",
        ],
    )
    return cap


@pytest.fixture
def mock_session_factory() -> MagicMock:
    sf = MagicMock()
    scope_cm = AsyncMock()
    scope_cm.__aenter__ = AsyncMock(return_value=None)
    scope_cm.__aexit__ = AsyncMock(return_value=False)
    sf.fund_scope.return_value = scope_cm
    return sf


@pytest.fixture
def order_repo() -> AsyncMock:
    repo = AsyncMock()
    return repo


@pytest.fixture
def compliance_gw() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def broker() -> StubBroker:
    return StubBroker(default_price=Decimal("150.00"))


@pytest.fixture
def order_fill_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(
    mock_session_factory: MagicMock,
    order_repo: AsyncMock,
    order_fill_repo: AsyncMock,
    compliance_gw: AsyncMock,
    broker: StubBroker,
    event_bus: InProcessEventBus,
) -> OrderService:
    return OrderService(
        session_factory=mock_session_factory,
        order_repo=order_repo,
        order_fill_repo=order_fill_repo,
        compliance_gateway=compliance_gw,
        broker=broker,
        event_bus=event_bus,
    )


# ---------------------------------------------------------------------------
# Create order — approved → filled (happy path)
# ---------------------------------------------------------------------------


class TestCreateOrderApproved:
    async def test_approved_order_reaches_filled_state(
        self,
        service: OrderService,
        order_repo: AsyncMock,
        compliance_gw: AsyncMock,
        capture: EventCapture,
    ):
        order_id = str(uuid4())
        portfolio_id = str(uuid4())

        # Mock compliance → approved
        compliance_gw.check.return_value = _approved_decision()

        # Track state transitions through save/update_state calls
        states_seen = []

        def save_side_effect(record, *, session=None):
            record.id = order_id
            record.portfolio_id = portfolio_id
            return record

        def update_state_side_effect(oid, new_state, *, session=None, **kwargs):
            states_seen.append(new_state)
            return _make_order_record(
                id=order_id,
                portfolio_id=portfolio_id,
                state=new_state,
                filled_quantity=kwargs.get("filled_quantity", Decimal("0")),
                avg_fill_price=kwargs.get("avg_fill_price"),
            )

        order_repo.insert.side_effect = save_side_effect
        order_repo.update_state.side_effect = update_state_side_effect

        request = make_order_request(portfolio_id=UUID(portfolio_id))
        result = await service.create_order(request, fund_slug="alpha", actor_id="trader1")

        assert result.state == OrderState.FILLED

    async def test_publishes_trade_executed_event(
        self,
        service: OrderService,
        order_repo: AsyncMock,
        compliance_gw: AsyncMock,
        capture: EventCapture,
    ):
        compliance_gw.check.return_value = _approved_decision()
        order_id = str(uuid4())
        order_repo.insert.side_effect = lambda r, **kw: setattr(r, "id", order_id) or r
        order_repo.update_state.side_effect = lambda oid, state, **kw: _make_order_record(
            id=order_id,
            state=state,
            filled_quantity=kw.get("filled_quantity", Decimal("0")),
            avg_fill_price=kw.get("avg_fill_price"),
        )

        request = make_order_request()
        await service.create_order(request, fund_slug="alpha", actor_id="trader1")

        trade_events = capture.get_by_topic("trades.executed")
        assert len(trade_events) == 1
        assert trade_events[0].data["instrument_id"] == "AAPL"

    async def test_publishes_order_created_and_trade_approved(
        self,
        service: OrderService,
        order_repo: AsyncMock,
        compliance_gw: AsyncMock,
        capture: EventCapture,
    ):
        compliance_gw.check.return_value = _approved_decision()
        order_id = str(uuid4())
        order_repo.insert.side_effect = lambda r, **kw: setattr(r, "id", order_id) or r
        order_repo.update_state.side_effect = lambda oid, state, **kw: _make_order_record(
            id=order_id, state=state
        )

        await service.create_order(make_order_request(), fund_slug="alpha", actor_id="t1")

        # Should publish to orders.created and trades.approved
        order_events = capture.get_by_topic("orders.created")
        approved_events = capture.get_by_topic("trades.approved")
        assert len(order_events) >= 1
        assert len(approved_events) >= 1


# ---------------------------------------------------------------------------
# Create order — rejected
# ---------------------------------------------------------------------------


class TestCreateOrderRejected:
    async def test_rejected_order_state(
        self,
        service: OrderService,
        order_repo: AsyncMock,
        compliance_gw: AsyncMock,
    ):
        compliance_gw.check.return_value = _rejected_decision()
        order_id = str(uuid4())
        order_repo.insert.side_effect = lambda r, **kw: setattr(r, "id", order_id) or r
        order_repo.update_state.side_effect = lambda oid, state, **kw: _make_order_record(
            id=order_id, state=state, rejection_reason=kw.get("rejection_reason")
        )

        result = await service.create_order(make_order_request(), fund_slug="alpha", actor_id="t1")
        assert result.state == OrderState.REJECTED

    async def test_rejected_publishes_trade_rejected(
        self,
        service: OrderService,
        order_repo: AsyncMock,
        compliance_gw: AsyncMock,
        capture: EventCapture,
    ):
        compliance_gw.check.return_value = _rejected_decision()
        order_id = str(uuid4())
        order_repo.insert.side_effect = lambda r, **kw: setattr(r, "id", order_id) or r
        order_repo.update_state.side_effect = lambda oid, state, **kw: _make_order_record(
            id=order_id, state=state
        )

        await service.create_order(make_order_request(), fund_slug="alpha", actor_id="t1")

        rejected_events = capture.get_by_topic("trades.rejected")
        assert len(rejected_events) >= 1

    async def test_rejected_does_not_submit_to_broker(
        self,
        service: OrderService,
        order_repo: AsyncMock,
        compliance_gw: AsyncMock,
        broker: StubBroker,
    ):
        compliance_gw.check.return_value = _rejected_decision()
        order_id = str(uuid4())
        order_repo.insert.side_effect = lambda r, **kw: setattr(r, "id", order_id) or r
        order_repo.update_state.side_effect = lambda oid, state, **kw: _make_order_record(
            id=order_id, state=state
        )

        # Spy on broker
        with patch.object(broker, "submit_order", wraps=broker.submit_order) as spy:
            await service.create_order(make_order_request(), fund_slug="alpha", actor_id="t1")
            spy.assert_not_called()


# ---------------------------------------------------------------------------
# Cancel order
# ---------------------------------------------------------------------------


class TestCancelOrder:
    async def test_cancel_sent_order(
        self,
        service: OrderService,
        order_repo: AsyncMock,
    ):
        oid = uuid4()
        order_repo.get_by_id.return_value = _make_order_record(
            id=str(oid), state=OrderState.SENT.value
        )
        order_repo.update_state.return_value = _make_order_record(
            id=str(oid), state=OrderState.CANCELLED.value
        )

        result = await service.cancel_order(oid)
        assert result.state == OrderState.CANCELLED

    async def test_cancel_filled_raises(
        self,
        service: OrderService,
        order_repo: AsyncMock,
    ):
        oid = uuid4()
        order_repo.get_by_id.return_value = _make_order_record(
            id=str(oid), state=OrderState.FILLED.value
        )

        with pytest.raises(InvalidTransitionError):
            await service.cancel_order(oid)

    async def test_cancel_rejected_raises(
        self,
        service: OrderService,
        order_repo: AsyncMock,
    ):
        oid = uuid4()
        order_repo.get_by_id.return_value = _make_order_record(
            id=str(oid), state=OrderState.REJECTED.value
        )

        with pytest.raises(InvalidTransitionError):
            await service.cancel_order(oid)

    async def test_cancel_nonexistent_raises(
        self,
        service: OrderService,
        order_repo: AsyncMock,
    ):
        order_repo.get_by_id.return_value = None
        with pytest.raises(LookupError):
            await service.cancel_order(uuid4())


# ---------------------------------------------------------------------------
# Get / list orders
# ---------------------------------------------------------------------------


class TestGetOrders:
    async def test_get_order_by_id(
        self,
        service: OrderService,
        order_repo: AsyncMock,
    ):
        oid = uuid4()
        order_repo.get_by_id.return_value = _make_order_record(
            id=str(oid), state=OrderState.FILLED.value
        )

        result = await service.get_order(oid)
        assert result.id == oid
        assert result.state == OrderState.FILLED

    async def test_get_nonexistent_raises(
        self,
        service: OrderService,
        order_repo: AsyncMock,
    ):
        order_repo.get_by_id.return_value = None
        with pytest.raises(LookupError):
            await service.get_order(uuid4())

    async def test_list_orders_by_portfolio(
        self,
        service: OrderService,
        order_repo: AsyncMock,
    ):
        pid = uuid4()
        order_repo.get_by_portfolio.return_value = [
            _make_order_record(id=str(uuid4()), portfolio_id=str(pid)),
            _make_order_record(id=str(uuid4()), portfolio_id=str(pid)),
        ]

        results = await service.get_orders(pid)
        assert len(results) == 2
