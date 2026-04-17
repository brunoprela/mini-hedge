"""Extended OrderService tests — algo orders, child orders, execution reports, routing, audit."""

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
from app.modules.orders.interfaces import (
    AlgoParams,
    AlgoType,
    CreateAlgoOrderRequest,
    OrderSide,
    OrderState,
    OrderType,
    TimeInForce,
)
from app.modules.orders.models.order import OrderRecord
from app.modules.orders.services import OrderService
from app.shared.events import InProcessEventBus
from tests.helpers import EventCapture, StubBroker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime.now(UTC)


def _make_order_record(**overrides) -> MagicMock:
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
        arrival_mid_price=None,
        arrival_spread=None,
        arrival_timestamp=None,
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


def _make_algo_request(
    portfolio_id: UUID | None = None,
    algo_type: AlgoType = AlgoType.TWAP,
) -> CreateAlgoOrderRequest:
    return CreateAlgoOrderRequest(
        portfolio_id=portfolio_id or uuid4(),
        instrument_id="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1000"),
        limit_price=Decimal("150.00"),
        algo_type=algo_type,
        algo_params=AlgoParams(duration_seconds=3600, num_slices=10),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
    return AsyncMock()


@pytest.fixture
def order_fill_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def compliance_gw() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def broker() -> StubBroker:
    return StubBroker(default_price=Decimal("150.00"))


@pytest.fixture
def audit_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def algo_engine() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def scorecard_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def market_data_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def routing_engine() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def broker_registry() -> MagicMock:
    return MagicMock()


def _make_service(
    *,
    session_factory,
    order_repo,
    order_fill_repo,
    compliance_gw,
    broker,
    event_bus,
    audit_repo=None,
    algo_engine=None,
    broker_registry=None,
    routing_engine=None,
    scorecard_service=None,
    market_data_service=None,
) -> OrderService:
    svc = OrderService(
        session_factory=session_factory,
        order_repo=order_repo,
        order_fill_repo=order_fill_repo,
        compliance_gateway=compliance_gw,
        broker=broker,
        event_bus=event_bus,
        audit_repo=audit_repo,
        broker_registry=broker_registry,
        routing_engine=routing_engine,
        scorecard_service=scorecard_service,
        market_data_service=market_data_service,
    )
    if algo_engine is not None:
        svc._algo_engine = algo_engine
    return svc


# ---------------------------------------------------------------------------
# create_algo_order — approved → working
# ---------------------------------------------------------------------------


class TestCreateAlgoOrderApproved:
    async def test_approved_algo_order_reaches_working_state(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
        audit_repo,
        algo_engine,
        capture,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
            audit_repo=audit_repo,
            algo_engine=algo_engine,
        )
        compliance_gw.check.return_value = _approved_decision()

        order_id = str(uuid4())
        portfolio_id = str(uuid4())

        def save_side_effect(record, *, session=None):
            record.id = order_id
            record.portfolio_id = portfolio_id
            return record

        def update_state_side_effect(oid, new_state, *, session=None, **kwargs):
            return _make_order_record(
                id=order_id,
                portfolio_id=portfolio_id,
                state=new_state,
                is_parent=True,
                algo_type="twap",
            )

        order_repo.insert.side_effect = save_side_effect
        order_repo.update_state.side_effect = update_state_side_effect

        request = _make_algo_request(portfolio_id=UUID(portfolio_id))
        result = await svc.create_algo_order(request, fund_slug="alpha", actor_id="t1")

        assert result.state == OrderState.WORKING
        algo_engine.start_algo.assert_awaited_once()
        audit_repo.insert_admin_event.assert_awaited()

    async def test_algo_order_publishes_events(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
        algo_engine,
        capture,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
            algo_engine=algo_engine,
        )
        compliance_gw.check.return_value = _approved_decision()
        order_id = str(uuid4())
        order_repo.insert.side_effect = lambda r, **kw: setattr(r, "id", order_id) or r
        order_repo.update_state.side_effect = lambda oid, state, **kw: _make_order_record(
            id=order_id, state=state, is_parent=True, algo_type="twap"
        )

        await svc.create_algo_order(_make_algo_request(), fund_slug="alpha", actor_id="t1")

        assert len(capture.get_by_topic("orders.created")) >= 1
        assert len(capture.get_by_topic("trades.approved")) >= 1


# ---------------------------------------------------------------------------
# create_algo_order — rejected
# ---------------------------------------------------------------------------


class TestCreateAlgoOrderRejected:
    async def test_rejected_algo_order(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
        audit_repo,
        algo_engine,
        capture,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
            audit_repo=audit_repo,
            algo_engine=algo_engine,
        )
        compliance_gw.check.return_value = _rejected_decision()
        order_id = str(uuid4())
        order_repo.insert.side_effect = lambda r, **kw: setattr(r, "id", order_id) or r
        order_repo.update_state.side_effect = lambda oid, state, **kw: _make_order_record(
            id=order_id,
            state=state,
            rejection_reason=kw.get("rejection_reason"),
            is_parent=True,
        )

        result = await svc.create_algo_order(_make_algo_request(), fund_slug="alpha", actor_id="t1")

        assert result.state == OrderState.REJECTED
        algo_engine.start_algo.assert_not_awaited()
        assert len(capture.get_by_topic("trades.rejected")) >= 1
        audit_repo.insert_admin_event.assert_awaited()


# ---------------------------------------------------------------------------
# create_algo_order — no engine configured
# ---------------------------------------------------------------------------


class TestCreateAlgoOrderNoEngine:
    async def test_raises_without_algo_engine(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
        )
        with pytest.raises(RuntimeError, match="AlgoEngine not configured"):
            await svc.create_algo_order(_make_algo_request(), fund_slug="alpha", actor_id="t1")


# ---------------------------------------------------------------------------
# create_child_order
# ---------------------------------------------------------------------------


class TestCreateChildOrder:
    async def test_child_order_happy_path(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
        )
        parent_id = str(uuid4())
        parent = _make_order_record(
            id=parent_id,
            state=OrderState.WORKING.value,
            is_parent=True,
            quantity=Decimal("1000"),
        )
        order_repo.get_by_id.return_value = parent

        child_id = str(uuid4())
        call_count = 0

        def save_side_effect(record, *, session=None):
            record.id = child_id
            return record

        def update_state_side_effect(oid, new_state, *, session=None, **kwargs):
            return _make_order_record(
                id=child_id,
                state=new_state,
                parent_order_id=parent_id,
                filled_quantity=kwargs.get("filled_quantity", Decimal("0")),
                avg_fill_price=kwargs.get("avg_fill_price"),
                quantity=Decimal("100"),
            )

        order_repo.insert.side_effect = save_side_effect
        order_repo.update_state.side_effect = update_state_side_effect
        # get_children for parent update
        order_repo.get_children.return_value = []

        result = await svc.create_child_order(
            parent_order_id=parent_id,
            quantity=Decimal("100"),
            fund_slug="alpha",
        )

        assert result is not None
        # Should have called submit_order on the broker
        assert order_repo.insert.await_count == 1

    async def test_child_order_parent_not_found(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
        )
        order_repo.get_by_id.return_value = None

        with pytest.raises(LookupError, match="not found"):
            await svc.create_child_order(
                parent_order_id=str(uuid4()),
                quantity=Decimal("100"),
                fund_slug="alpha",
            )


# ---------------------------------------------------------------------------
# process_execution_report
# ---------------------------------------------------------------------------


class TestProcessExecutionReport:
    async def test_execution_report_fills_order(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
        audit_repo,
        capture,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
            audit_repo=audit_repo,
        )
        svc._fund_slugs = ["alpha"]

        order_id = str(uuid4())
        sent_order = _make_order_record(
            id=order_id,
            state=OrderState.SENT.value,
            quantity=Decimal("100"),
            filled_quantity=Decimal("0"),
            fund_slug="alpha",
            parent_order_id=None,
            broker_id=None,
        )
        order_repo.get_by_id.return_value = sent_order

        filled_order = _make_order_record(
            id=order_id,
            state=OrderState.FILLED.value,
            quantity=Decimal("100"),
            filled_quantity=Decimal("100"),
            fund_slug="alpha",
            parent_order_id=None,
        )
        order_repo.update_state.return_value = filled_order

        await svc.process_execution_report(
            client_order_id=order_id,
            fill_price=Decimal("150.00"),
            fill_quantity=Decimal("100"),
        )

        order_fill_repo.insert_fill.assert_awaited_once()
        order_repo.update_state.assert_awaited()
        audit_repo.insert_admin_event.assert_awaited()

    @patch("app.modules.orders.services.order.asyncio.sleep", new_callable=AsyncMock)
    async def test_execution_report_unknown_order(
        self,
        mock_sleep,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
        )
        svc._fund_slugs = ["alpha"]
        order_repo.get_by_id.return_value = None

        # Should not raise — just logs warning
        await svc.process_execution_report(
            client_order_id=str(uuid4()),
            fill_price=Decimal("150.00"),
            fill_quantity=Decimal("100"),
        )

        order_fill_repo.insert_fill.assert_not_awaited()

    @patch("app.modules.orders.services.order.asyncio.sleep", new_callable=AsyncMock)
    async def test_execution_report_invalid_state(
        self,
        mock_sleep,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
        )
        svc._fund_slugs = ["alpha"]

        # Order already filled — invalid state for execution report
        order_repo.get_by_id.return_value = _make_order_record(
            state=OrderState.FILLED.value,
        )

        await svc.process_execution_report(
            client_order_id=str(uuid4()),
            fill_price=Decimal("150.00"),
            fill_quantity=Decimal("100"),
        )

        order_fill_repo.insert_fill.assert_not_awaited()

    async def test_execution_report_partially_filled_state(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
        capture,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
        )
        svc._fund_slugs = ["alpha"]

        order_id = str(uuid4())
        partial_order = _make_order_record(
            id=order_id,
            state=OrderState.PARTIALLY_FILLED.value,
            quantity=Decimal("100"),
            filled_quantity=Decimal("50"),
            avg_fill_price=Decimal("149.00"),
            fund_slug="alpha",
            parent_order_id=None,
            broker_id=None,
        )
        order_repo.get_by_id.return_value = partial_order
        order_repo.update_state.return_value = _make_order_record(
            id=order_id,
            state=OrderState.FILLED.value,
            quantity=Decimal("100"),
            filled_quantity=Decimal("100"),
            parent_order_id=None,
        )

        await svc.process_execution_report(
            client_order_id=order_id,
            fill_price=Decimal("151.00"),
            fill_quantity=Decimal("50"),
            broker_id="broker-1",
        )

        order_fill_repo.insert_fill.assert_awaited_once()


# ---------------------------------------------------------------------------
# cancel parent algo order — with children
# ---------------------------------------------------------------------------


class TestCancelAlgoOrder:
    async def test_cancel_parent_cancels_children(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
        algo_engine,
        audit_repo,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
            algo_engine=algo_engine,
            audit_repo=audit_repo,
        )

        parent_id = uuid4()
        child1 = _make_order_record(id=str(uuid4()), state=OrderState.SENT.value)
        child2 = _make_order_record(id=str(uuid4()), state=OrderState.APPROVED.value)

        order_repo.get_by_id.return_value = _make_order_record(
            id=str(parent_id),
            state=OrderState.WORKING.value,
            is_parent=True,
            fund_slug="alpha",
        )
        order_repo.get_active_children.return_value = [child1, child2]
        order_repo.update_state.return_value = _make_order_record(
            id=str(parent_id), state=OrderState.CANCELLED.value, fund_slug="alpha"
        )

        result = await svc.cancel_order(parent_id)

        assert result.state == OrderState.CANCELLED
        algo_engine.cancel_algo.assert_awaited_once()
        # 2 children + 1 parent = at least 3 update_state calls
        assert order_repo.update_state.await_count >= 3

    async def test_cancel_parent_handles_child_cancel_failure(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
        algo_engine,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
            algo_engine=algo_engine,
        )

        parent_id = uuid4()
        # Child in FILLED state — transition to CANCELLED will fail
        filled_child = _make_order_record(id=str(uuid4()), state=OrderState.FILLED.value)

        order_repo.get_by_id.return_value = _make_order_record(
            id=str(parent_id),
            state=OrderState.WORKING.value,
            is_parent=True,
            fund_slug="alpha",
        )
        order_repo.get_active_children.return_value = [filled_child]
        order_repo.update_state.return_value = _make_order_record(
            id=str(parent_id), state=OrderState.CANCELLED.value, fund_slug="alpha"
        )

        # Should not raise — child cancel failure is logged and ignored
        result = await svc.cancel_order(parent_id)
        assert result.state == OrderState.CANCELLED


# ---------------------------------------------------------------------------
# get_children / get_fills
# ---------------------------------------------------------------------------


class TestGetChildrenAndFills:
    async def test_get_children(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
        )
        parent_id = uuid4()
        child1 = _make_order_record(id=str(uuid4()), parent_order_id=str(parent_id))
        child2 = _make_order_record(id=str(uuid4()), parent_order_id=str(parent_id))
        order_repo.get_children.return_value = [child1, child2]

        results = await svc.get_children(parent_id)
        assert len(results) == 2

    async def test_get_fills(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
        )
        order_id = uuid4()
        fill = MagicMock()
        fill.id = str(uuid4())
        fill.order_id = str(order_id)
        fill.quantity = Decimal("100")
        fill.price = Decimal("150.00")
        fill.broker_id = "broker-1"
        fill.commission = Decimal("0.50")
        fill.venue = "NYSE"
        fill.filled_at = NOW

        order_fill_repo.get_fills.return_value = [fill]

        results = await svc.get_fills(order_id)
        assert len(results) == 1
        assert results[0].price == Decimal("150.00")
        assert results[0].broker_id == "broker-1"


# ---------------------------------------------------------------------------
# _process_fill with scorecard, VWAP, TCA, parent update
# ---------------------------------------------------------------------------


class TestProcessFillExtended:
    async def test_process_fill_with_scorecard(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
        scorecard_service,
        capture,
    ):
        """Fill with scorecard service records fill metrics."""
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
            scorecard_service=scorecard_service,
        )

        order = _make_order_record(
            state=OrderState.SENT.value,
            quantity=Decimal("100"),
            filled_quantity=Decimal("0"),
            broker_id="broker-1",
            parent_order_id=None,
        )
        order_repo.update_state.return_value = _make_order_record(
            state=OrderState.FILLED.value,
            quantity=Decimal("100"),
            filled_quantity=Decimal("100"),
            parent_order_id=None,
        )

        await svc._process_fill(
            order,
            fill_price=Decimal("150.00"),
            fill_quantity=Decimal("100"),
            fund_slug="alpha",
            broker_id="broker-1",
        )

        scorecard_service.record_fill.assert_awaited_once()

    async def test_process_fill_scorecard_failure_ignored(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
        scorecard_service,
    ):
        """Scorecard errors are fire-and-forget — should not raise."""
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
            scorecard_service=scorecard_service,
        )

        scorecard_service.record_fill.side_effect = RuntimeError("DB error")

        order = _make_order_record(
            state=OrderState.SENT.value,
            quantity=Decimal("100"),
            filled_quantity=Decimal("0"),
            broker_id="broker-1",
            parent_order_id=None,
        )
        order_repo.update_state.return_value = _make_order_record(
            state=OrderState.FILLED.value, parent_order_id=None
        )

        # Should not raise
        await svc._process_fill(
            order,
            fill_price=Decimal("150.00"),
            fill_quantity=Decimal("100"),
            fund_slug="alpha",
            broker_id="broker-1",
        )

    async def test_process_fill_vwap_calculation(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
        capture,
    ):
        """Second fill computes VWAP across both fills."""
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
        )

        order = _make_order_record(
            state=OrderState.PARTIALLY_FILLED.value,
            quantity=Decimal("200"),
            filled_quantity=Decimal("100"),
            avg_fill_price=Decimal("148.00"),
            parent_order_id=None,
        )
        order_repo.update_state.return_value = _make_order_record(
            state=OrderState.FILLED.value,
            quantity=Decimal("200"),
            filled_quantity=Decimal("200"),
            avg_fill_price=Decimal("149.00"),
            parent_order_id=None,
        )

        result = await svc._process_fill(
            order,
            fill_price=Decimal("150.00"),
            fill_quantity=Decimal("100"),
            fund_slug="alpha",
        )

        # Verify update_state was called with VWAP
        call_kwargs = order_repo.update_state.call_args
        assert call_kwargs.kwargs["avg_fill_price"] == Decimal("149.00")

    async def test_process_fill_partial(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
    ):
        """Partial fill transitions to PARTIALLY_FILLED."""
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
        )

        order = _make_order_record(
            state=OrderState.SENT.value,
            quantity=Decimal("200"),
            filled_quantity=Decimal("0"),
            parent_order_id=None,
        )
        order_repo.update_state.return_value = _make_order_record(
            state=OrderState.PARTIALLY_FILLED.value,
            quantity=Decimal("200"),
            filled_quantity=Decimal("50"),
            parent_order_id=None,
        )

        result = await svc._process_fill(
            order,
            fill_price=Decimal("150.00"),
            fill_quantity=Decimal("50"),
            fund_slug="alpha",
        )

        assert result.state == OrderState.PARTIALLY_FILLED.value

    @patch("app.modules.orders.services.order.asyncio.create_task")
    async def test_process_fill_triggers_tca(
        self,
        mock_create_task,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
    ):
        """Full fill triggers TCA computation."""
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
        )
        tca_service = AsyncMock()
        svc._tca_service = tca_service

        order = _make_order_record(
            state=OrderState.SENT.value,
            quantity=Decimal("100"),
            filled_quantity=Decimal("0"),
            parent_order_id=None,
        )
        order_repo.update_state.return_value = _make_order_record(
            state=OrderState.FILLED.value,
            quantity=Decimal("100"),
            filled_quantity=Decimal("100"),
            parent_order_id=None,
        )

        await svc._process_fill(
            order,
            fill_price=Decimal("150.00"),
            fill_quantity=Decimal("100"),
            fund_slug="alpha",
        )

        mock_create_task.assert_called_once()

    async def test_process_fill_updates_parent(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
    ):
        """Fill on a child order triggers parent state update."""
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
        )

        parent_id = str(uuid4())
        child_order = _make_order_record(
            state=OrderState.SENT.value,
            quantity=Decimal("100"),
            filled_quantity=Decimal("0"),
            parent_order_id=parent_id,
        )

        filled_child = _make_order_record(
            state=OrderState.FILLED.value,
            quantity=Decimal("100"),
            filled_quantity=Decimal("100"),
            avg_fill_price=Decimal("150.00"),
            parent_order_id=parent_id,
        )

        parent = _make_order_record(
            id=parent_id,
            state=OrderState.WORKING.value,
            is_parent=True,
            quantity=Decimal("100"),
            filled_quantity=Decimal("0"),
        )

        order_repo.update_state.return_value = filled_child
        order_repo.get_by_id.return_value = parent
        order_repo.get_children.return_value = [filled_child]

        await svc._process_fill(
            child_order,
            fill_price=Decimal("150.00"),
            fill_quantity=Decimal("100"),
            fund_slug="alpha",
        )

        # Parent should have been updated
        assert order_repo.get_children.await_count >= 1


# ---------------------------------------------------------------------------
# _update_parent_from_children
# ---------------------------------------------------------------------------


class TestUpdateParentFromChildren:
    async def test_parent_not_found_returns_early(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
        )
        order_repo.get_by_id.return_value = None

        # Should not raise
        await svc._update_parent_from_children(uuid4(), "alpha")

    async def test_no_children_returns_early(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
        )
        parent = _make_order_record(state=OrderState.WORKING.value)
        order_repo.get_by_id.return_value = parent
        order_repo.get_children.return_value = []

        await svc._update_parent_from_children(uuid4(), "alpha")
        order_repo.update_state.assert_not_awaited()

    async def test_all_children_filled_updates_parent_to_filled(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
        )

        parent_id = uuid4()
        parent = _make_order_record(
            id=str(parent_id), state=OrderState.WORKING.value, is_parent=True
        )
        child1 = _make_order_record(
            state=OrderState.FILLED.value,
            filled_quantity=Decimal("50"),
            avg_fill_price=Decimal("150.00"),
        )
        child2 = _make_order_record(
            state=OrderState.FILLED.value,
            filled_quantity=Decimal("50"),
            avg_fill_price=Decimal("151.00"),
        )

        order_repo.get_by_id.return_value = parent
        order_repo.get_children.return_value = [child1, child2]

        await svc._update_parent_from_children(parent_id, "alpha")

        order_repo.update_state.assert_awaited_once()
        call_args = order_repo.update_state.call_args
        assert call_args[0][1] == OrderState.FILLED.value
        assert call_args.kwargs["filled_quantity"] == Decimal("100")

    async def test_mixed_children_updates_parent_to_partially_filled(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
        )

        parent_id = uuid4()
        parent = _make_order_record(
            id=str(parent_id), state=OrderState.WORKING.value, is_parent=True
        )
        child1 = _make_order_record(
            state=OrderState.FILLED.value,
            filled_quantity=Decimal("50"),
            avg_fill_price=Decimal("150.00"),
        )
        child2 = _make_order_record(
            state=OrderState.SENT.value,
            filled_quantity=Decimal("0"),
            avg_fill_price=None,
        )

        order_repo.get_by_id.return_value = parent
        order_repo.get_children.return_value = [child1, child2]

        await svc._update_parent_from_children(parent_id, "alpha")

        call_args = order_repo.update_state.call_args
        assert call_args[0][1] == OrderState.PARTIALLY_FILLED.value

    async def test_invalid_parent_transition_skipped(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
    ):
        """If parent state transition is invalid, skip the update gracefully."""
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
        )

        parent_id = uuid4()
        # Parent already CANCELLED — transitioning to FILLED is invalid
        parent = _make_order_record(
            id=str(parent_id), state=OrderState.CANCELLED.value, is_parent=True
        )
        child1 = _make_order_record(
            state=OrderState.FILLED.value,
            filled_quantity=Decimal("50"),
            avg_fill_price=Decimal("150.00"),
        )

        order_repo.get_by_id.return_value = parent
        order_repo.get_children.return_value = [child1]

        # Should not raise — logs warning and returns
        await svc._update_parent_from_children(parent_id, "alpha")
        order_repo.update_state.assert_not_awaited()


# ---------------------------------------------------------------------------
# create_order with routing engine
# ---------------------------------------------------------------------------


class TestCreateOrderWithRouting:
    async def test_routes_through_routing_engine(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
        routing_engine,
        broker_registry,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
            routing_engine=routing_engine,
            broker_registry=broker_registry,
        )

        compliance_gw.check.return_value = _approved_decision()

        order_id = str(uuid4())
        order_repo.insert.side_effect = lambda r, **kw: setattr(r, "id", order_id) or r

        def update_state_side_effect(oid, new_state, *, session=None, **kwargs):
            return _make_order_record(
                id=order_id,
                state=new_state,
                filled_quantity=kwargs.get("filled_quantity", Decimal("0")),
                avg_fill_price=kwargs.get("avg_fill_price"),
                broker_id=kwargs.get("broker_id"),
            )

        order_repo.update_state.side_effect = update_state_side_effect

        # Routing engine returns a single slice
        slice_mock = MagicMock()
        slice_mock.broker_id = "broker-prime"
        routing_engine.route_order.return_value = [slice_mock]

        # Broker registry returns a different broker adapter
        alt_broker = StubBroker(default_price=Decimal("151.00"))
        broker_registry.get.return_value = alt_broker

        from tests.factories import make_order_request

        result = await svc.create_order(make_order_request(), fund_slug="alpha", actor_id="t1")

        routing_engine.route_order.assert_awaited_once()
        broker_registry.get.assert_called_with("broker-prime")

    async def test_routing_broker_not_found_falls_back(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
        routing_engine,
        broker_registry,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
            routing_engine=routing_engine,
            broker_registry=broker_registry,
        )

        compliance_gw.check.return_value = _approved_decision()
        order_id = str(uuid4())
        order_repo.insert.side_effect = lambda r, **kw: setattr(r, "id", order_id) or r
        order_repo.update_state.side_effect = lambda oid, state, **kw: _make_order_record(
            id=order_id,
            state=state,
            filled_quantity=kw.get("filled_quantity", Decimal("0")),
            avg_fill_price=kw.get("avg_fill_price"),
        )

        slice_mock = MagicMock()
        slice_mock.broker_id = "unknown-broker"
        routing_engine.route_order.return_value = [slice_mock]
        broker_registry.get.side_effect = KeyError("unknown-broker")

        from tests.factories import make_order_request

        # Should fall back to default broker, not raise
        result = await svc.create_order(make_order_request(), fund_slug="alpha", actor_id="t1")
        assert result.state == OrderState.FILLED


# ---------------------------------------------------------------------------
# create_order with market data (arrival price capture)
# ---------------------------------------------------------------------------


class TestCreateOrderWithMarketData:
    async def test_captures_arrival_price(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
        market_data_service,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
            market_data_service=market_data_service,
        )
        compliance_gw.check.return_value = _approved_decision()

        snap = MagicMock()
        snap.mid = Decimal("150.50")
        snap.ask = Decimal("151.00")
        snap.bid = Decimal("150.00")
        snap.timestamp = NOW
        market_data_service.get_latest_price.return_value = snap

        order_id = str(uuid4())
        order_repo.insert.side_effect = lambda r, **kw: setattr(r, "id", order_id) or r
        order_repo.update_state.side_effect = lambda oid, state, **kw: _make_order_record(
            id=order_id,
            state=state,
            filled_quantity=kw.get("filled_quantity", Decimal("0")),
            avg_fill_price=kw.get("avg_fill_price"),
        )

        from tests.factories import make_order_request

        await svc.create_order(make_order_request(), fund_slug="alpha", actor_id="t1")

        market_data_service.get_latest_price.assert_awaited_once()

    async def test_no_price_snapshot_continues(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
        market_data_service,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
            market_data_service=market_data_service,
        )
        compliance_gw.check.return_value = _approved_decision()
        market_data_service.get_latest_price.return_value = None

        order_id = str(uuid4())
        order_repo.insert.side_effect = lambda r, **kw: setattr(r, "id", order_id) or r
        order_repo.update_state.side_effect = lambda oid, state, **kw: _make_order_record(
            id=order_id,
            state=state,
            filled_quantity=kw.get("filled_quantity", Decimal("0")),
            avg_fill_price=kw.get("avg_fill_price"),
        )

        from tests.factories import make_order_request

        result = await svc.create_order(make_order_request(), fund_slug="alpha", actor_id="t1")
        assert result.state == OrderState.FILLED


# ---------------------------------------------------------------------------
# create_order — broker rejection
# ---------------------------------------------------------------------------


class TestCreateOrderBrokerRejection:
    async def test_broker_rejects_order(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        event_bus,
    ):
        """When broker returns status=rejected, order is cancelled."""
        from app.shared.adapters.broker import OrderAcknowledgement

        # Custom broker that rejects
        rejecting_broker = AsyncMock()
        rejecting_broker.submit_order.return_value = OrderAcknowledgement(
            exchange_order_id="exch-1",
            client_order_id="test",
            status="rejected",
            received_at=NOW,
        )

        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=rejecting_broker,
            event_bus=event_bus,
        )

        compliance_gw.check.return_value = _approved_decision()
        order_id = str(uuid4())
        order_repo.insert.side_effect = lambda r, **kw: setattr(r, "id", order_id) or r
        order_repo.update_state.side_effect = lambda oid, state, **kw: _make_order_record(
            id=order_id,
            state=state,
            rejection_reason=kw.get("rejection_reason"),
        )

        from tests.factories import make_order_request

        result = await svc.create_order(make_order_request(), fund_slug="alpha", actor_id="t1")
        assert result.state == OrderState.CANCELLED

    async def test_broker_async_ack(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        event_bus,
    ):
        """When broker returns status=ack (async), order stays SENT."""
        from app.shared.adapters.broker import OrderAcknowledgement

        async_broker = AsyncMock()
        async_broker.submit_order.return_value = OrderAcknowledgement(
            exchange_order_id="exch-1",
            client_order_id="test",
            status="ack",
            received_at=NOW,
        )

        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=async_broker,
            event_bus=event_bus,
        )

        compliance_gw.check.return_value = _approved_decision()
        order_id = str(uuid4())
        order_repo.insert.side_effect = lambda r, **kw: setattr(r, "id", order_id) or r
        order_repo.update_state.side_effect = lambda oid, state, **kw: _make_order_record(
            id=order_id, state=state
        )

        from tests.factories import make_order_request

        result = await svc.create_order(make_order_request(), fund_slug="alpha", actor_id="t1")
        assert result.state == OrderState.SENT


# ---------------------------------------------------------------------------
# _audit_event
# ---------------------------------------------------------------------------


class TestAuditEvent:
    async def test_audit_event_with_repo(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
        audit_repo,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
            audit_repo=audit_repo,
        )

        from app.shared.audit.events import AuditEventType

        order = _make_order_record()
        await svc._audit_event(
            AuditEventType.ORDER_CREATED,
            actor_id="trader1",
            fund_slug="alpha",
            order=order,
            extra={"test_key": "test_value"},
        )

        audit_repo.insert_admin_event.assert_awaited_once()
        call_kwargs = audit_repo.insert_admin_event.call_args.kwargs
        assert call_kwargs["actor_id"] == "trader1"
        assert call_kwargs["fund_slug"] == "alpha"
        assert "test_key" in call_kwargs["payload"]

    async def test_audit_event_without_repo_noop(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
        )

        from app.shared.audit.events import AuditEventType

        order = _make_order_record()
        # Should not raise
        await svc._audit_event(
            AuditEventType.ORDER_CREATED,
            actor_id="trader1",
            fund_slug="alpha",
            order=order,
        )


# ---------------------------------------------------------------------------
# create_algo_order with market data
# ---------------------------------------------------------------------------


class TestCreateAlgoOrderWithMarketData:
    async def test_algo_order_captures_arrival_price(
        self,
        mock_session_factory,
        order_repo,
        order_fill_repo,
        compliance_gw,
        broker,
        event_bus,
        algo_engine,
        market_data_service,
    ):
        svc = _make_service(
            session_factory=mock_session_factory,
            order_repo=order_repo,
            order_fill_repo=order_fill_repo,
            compliance_gw=compliance_gw,
            broker=broker,
            event_bus=event_bus,
            algo_engine=algo_engine,
            market_data_service=market_data_service,
        )
        compliance_gw.check.return_value = _approved_decision()

        snap = MagicMock()
        snap.mid = Decimal("150.50")
        snap.ask = Decimal("151.00")
        snap.bid = Decimal("150.00")
        snap.timestamp = NOW
        market_data_service.get_latest_price.return_value = snap

        order_id = str(uuid4())
        order_repo.insert.side_effect = lambda r, **kw: setattr(r, "id", order_id) or r
        order_repo.update_state.side_effect = lambda oid, state, **kw: _make_order_record(
            id=order_id,
            state=state,
            is_parent=True,
            algo_type="twap",
        )

        result = await svc.create_algo_order(
            _make_algo_request(), fund_slug="alpha", actor_id="t1"
        )

        market_data_service.get_latest_price.assert_awaited_once()
        assert result.state == OrderState.WORKING
