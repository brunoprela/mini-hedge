"""Unit tests for TradeHandler — _apply_trade, _apply_corporate_action, handle_trade, _publish_downstream."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.positions.core.trade_handler import TradeHandler
from app.modules.positions.interfaces import (
    PnLMarkToMarket,
    PnLMarkToMarketData,
    PnLRealized,
    PnLRealizedData,
    PositionChanged,
    PositionChangedData,
    PositionEventType,
    TradeSide,
)
from app.shared.events import InProcessEventBus
from app.shared.schema_registry import fund_topic
from tests.factories import DEFAULT_PORTFOLIO_ID, make_trades_executed_event
from tests.helpers import EventCapture

_PORT_ID = DEFAULT_PORTFOLIO_ID


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_session_factory() -> MagicMock:
    sf = MagicMock()
    # fund_scope returns an async context manager
    scope_cm = AsyncMock()
    scope_cm.__aenter__ = AsyncMock(return_value=None)
    scope_cm.__aexit__ = AsyncMock(return_value=False)
    sf.fund_scope.return_value = scope_cm

    # __call__ returns an async context manager yielding a mock session
    mock_session = AsyncMock()
    session_cm = AsyncMock()
    session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    session_cm.__aexit__ = AsyncMock(return_value=False)
    sf.return_value = session_cm
    sf._mock_session = mock_session
    return sf


def _make_handler(
    *,
    event_store: AsyncMock | None = None,
    projector: AsyncMock | None = None,
    event_bus: InProcessEventBus | None = None,
    session_factory: MagicMock | None = None,
) -> TradeHandler:
    return TradeHandler(
        session_factory=session_factory or _make_session_factory(),
        event_store=event_store or AsyncMock(
            get_by_aggregate=AsyncMock(return_value=[]),
            has_idempotency_key=AsyncMock(return_value=False),
            append=AsyncMock(),
        ),
        projector=projector or AsyncMock(),
        event_bus=event_bus or InProcessEventBus(),
    )


# ---------------------------------------------------------------------------
# Tests: _apply_trade
# ---------------------------------------------------------------------------


class TestApplyTrade:
    async def test_applies_trade_and_persists(self) -> None:
        """_apply_trade loads events, applies to aggregate, appends, and projects."""
        sf = _make_session_factory()
        store = AsyncMock()
        store.get_by_aggregate = AsyncMock(return_value=[])
        store.has_idempotency_key = AsyncMock(return_value=False)
        store.append = AsyncMock()
        projector = AsyncMock()

        handler = _make_handler(session_factory=sf, event_store=store, projector=projector)

        result = await handler._apply_trade(
            fund_slug="alpha",
            portfolio_id=_PORT_ID,
            instrument_id="AAPL",
            side=TradeSide.BUY,
            quantity=Decimal("100"),
            price=Decimal("150.00"),
            currency="USD",
            trade_id=DEFAULT_PORTFOLIO_ID,  # reuse a UUID
        )

        assert result is not None
        assert isinstance(result, list)
        store.get_by_aggregate.assert_called_once()
        store.append.assert_called_once()
        projector.project.assert_called_once()

    async def test_idempotent_duplicate_returns_none(self) -> None:
        """When idempotency key already exists, _apply_trade returns None."""
        store = AsyncMock()
        store.has_idempotency_key = AsyncMock(return_value=True)
        store.get_by_aggregate = AsyncMock(return_value=[])

        handler = _make_handler(event_store=store)

        result = await handler._apply_trade(
            fund_slug="alpha",
            portfolio_id=_PORT_ID,
            instrument_id="AAPL",
            side=TradeSide.BUY,
            quantity=Decimal("100"),
            price=Decimal("150.00"),
            currency="USD",
            trade_id=DEFAULT_PORTFOLIO_ID,
            idempotency_key="dup-key-123",
        )

        assert result is None

    async def test_retries_on_integrity_error(self) -> None:
        """_apply_trade retries up to 3 times on IntegrityError."""
        sf = _make_session_factory()
        store = AsyncMock()
        store.get_by_aggregate = AsyncMock(return_value=[])
        store.has_idempotency_key = AsyncMock(return_value=False)
        # Fail first two times, succeed third
        store.append = AsyncMock(
            side_effect=[
                IntegrityError("conflict", params=None, orig=Exception()),
                IntegrityError("conflict", params=None, orig=Exception()),
                None,
            ]
        )
        projector = AsyncMock()
        handler = _make_handler(session_factory=sf, event_store=store, projector=projector)

        result = await handler._apply_trade(
            fund_slug="alpha",
            portfolio_id=_PORT_ID,
            instrument_id="AAPL",
            side=TradeSide.BUY,
            quantity=Decimal("100"),
            price=Decimal("150.00"),
            currency="USD",
            trade_id=DEFAULT_PORTFOLIO_ID,
        )

        assert result is not None
        assert store.append.call_count == 3

    async def test_exhausted_retries_raises(self) -> None:
        """After max retries, IntegrityError is re-raised."""
        sf = _make_session_factory()
        store = AsyncMock()
        store.get_by_aggregate = AsyncMock(return_value=[])
        store.has_idempotency_key = AsyncMock(return_value=False)
        store.append = AsyncMock(
            side_effect=IntegrityError("conflict", params=None, orig=Exception())
        )
        projector = AsyncMock()
        handler = _make_handler(session_factory=sf, event_store=store, projector=projector)

        with pytest.raises(IntegrityError):
            await handler._apply_trade(
                fund_slug="alpha",
                portfolio_id=_PORT_ID,
                instrument_id="AAPL",
                side=TradeSide.BUY,
                quantity=Decimal("100"),
                price=Decimal("150.00"),
                currency="USD",
                trade_id=DEFAULT_PORTFOLIO_ID,
            )

    async def test_sell_side_event_type(self) -> None:
        """Selling creates TRADE_SELL event type."""
        sf = _make_session_factory()
        store = AsyncMock()
        store.get_by_aggregate = AsyncMock(return_value=[])
        store.has_idempotency_key = AsyncMock(return_value=False)
        store.append = AsyncMock()
        projector = AsyncMock()
        handler = _make_handler(session_factory=sf, event_store=store, projector=projector)

        result = await handler._apply_trade(
            fund_slug="alpha",
            portfolio_id=_PORT_ID,
            instrument_id="AAPL",
            side=TradeSide.SELL,
            quantity=Decimal("50"),
            price=Decimal("160.00"),
            currency="USD",
            trade_id=DEFAULT_PORTFOLIO_ID,
        )

        assert result is not None


# ---------------------------------------------------------------------------
# Tests: _apply_corporate_action
# ---------------------------------------------------------------------------


class TestApplyCorporateAction:
    async def test_applies_stock_split(self) -> None:
        sf = _make_session_factory()
        store = AsyncMock()
        store.get_by_aggregate = AsyncMock(return_value=[])
        store.has_idempotency_key = AsyncMock(return_value=False)
        store.append = AsyncMock()
        projector = AsyncMock()
        handler = _make_handler(session_factory=sf, event_store=store, projector=projector)

        event = make_trades_executed_event(fund_slug="alpha")
        event = event.model_copy(
            update={
                "event_type": "corporate_action.split",
                "data": {
                    "portfolio_id": str(_PORT_ID),
                    "instrument_id": "AAPL",
                    "action_id": str(DEFAULT_PORTFOLIO_ID),
                    "currency": "USD",
                    "quantity": "2",
                    "source": "corporate_action",
                },
            }
        )

        result = await handler._apply_corporate_action(fund_slug="alpha", event=event)

        assert result is not None
        store.append.assert_called_once()
        projector.project.assert_called_once()

    async def test_applies_dividend(self) -> None:
        sf = _make_session_factory()
        store = AsyncMock()
        store.get_by_aggregate = AsyncMock(return_value=[])
        store.has_idempotency_key = AsyncMock(return_value=False)
        store.append = AsyncMock()
        projector = AsyncMock()
        handler = _make_handler(session_factory=sf, event_store=store, projector=projector)

        event = make_trades_executed_event(fund_slug="alpha")
        event = event.model_copy(
            update={
                "event_type": "corporate_action.dividend",
                "data": {
                    "portfolio_id": str(_PORT_ID),
                    "instrument_id": "AAPL",
                    "action_id": str(DEFAULT_PORTFOLIO_ID),
                    "currency": "USD",
                    "quantity": "500",
                    "source": "corporate_action",
                },
            }
        )

        result = await handler._apply_corporate_action(fund_slug="alpha", event=event)

        assert result is not None

    async def test_idempotent_duplicate_returns_none(self) -> None:
        sf = _make_session_factory()
        store = AsyncMock()
        store.has_idempotency_key = AsyncMock(return_value=True)
        store.get_by_aggregate = AsyncMock(return_value=[])
        handler = _make_handler(session_factory=sf, event_store=store)

        event = make_trades_executed_event(fund_slug="alpha")
        event = event.model_copy(
            update={
                "event_type": "corporate_action.split",
                "data": {
                    "portfolio_id": str(_PORT_ID),
                    "instrument_id": "AAPL",
                    "action_id": str(DEFAULT_PORTFOLIO_ID),
                    "currency": "USD",
                    "quantity": "2",
                    "source": "corporate_action",
                },
            }
        )

        result = await handler._apply_corporate_action(fund_slug="alpha", event=event)

        assert result is None

    async def test_corporate_action_retries_on_integrity_error(self) -> None:
        sf = _make_session_factory()
        store = AsyncMock()
        store.get_by_aggregate = AsyncMock(return_value=[])
        store.has_idempotency_key = AsyncMock(return_value=False)
        store.append = AsyncMock(
            side_effect=[
                IntegrityError("conflict", params=None, orig=Exception()),
                IntegrityError("conflict", params=None, orig=Exception()),
                None,
            ]
        )
        projector = AsyncMock()
        handler = _make_handler(session_factory=sf, event_store=store, projector=projector)

        event = make_trades_executed_event(fund_slug="alpha")
        event = event.model_copy(
            update={
                "event_type": "corporate_action.split",
                "data": {
                    "portfolio_id": str(_PORT_ID),
                    "instrument_id": "AAPL",
                    "action_id": str(DEFAULT_PORTFOLIO_ID),
                    "currency": "USD",
                    "quantity": "2",
                    "source": "corporate_action",
                },
            }
        )

        result = await handler._apply_corporate_action(fund_slug="alpha", event=event)

        assert result is not None
        assert store.append.call_count == 3

    async def test_corporate_action_exhausted_retries_raises(self) -> None:
        sf = _make_session_factory()
        store = AsyncMock()
        store.get_by_aggregate = AsyncMock(return_value=[])
        store.has_idempotency_key = AsyncMock(return_value=False)
        store.append = AsyncMock(
            side_effect=IntegrityError("conflict", params=None, orig=Exception())
        )
        projector = AsyncMock()
        handler = _make_handler(session_factory=sf, event_store=store, projector=projector)

        event = make_trades_executed_event(fund_slug="alpha")
        event = event.model_copy(
            update={
                "event_type": "corporate_action.split",
                "data": {
                    "portfolio_id": str(_PORT_ID),
                    "instrument_id": "AAPL",
                    "action_id": str(DEFAULT_PORTFOLIO_ID),
                    "currency": "USD",
                    "quantity": "2",
                    "source": "corporate_action",
                },
            }
        )

        with pytest.raises(IntegrityError):
            await handler._apply_corporate_action(fund_slug="alpha", event=event)


# ---------------------------------------------------------------------------
# Tests: handle_trade (direct call path)
# ---------------------------------------------------------------------------


class TestHandleTrade:
    async def test_publishes_trade_and_downstream(self) -> None:
        """handle_trade publishes trades.executed AND downstream events."""
        bus = InProcessEventBus()
        cap = EventCapture()
        cap.wire_to_bus(
            bus,
            [
                fund_topic("alpha", "trades.executed"),
                fund_topic("alpha", "positions.changed"),
                fund_topic("alpha", "pnl.updated"),
            ],
        )

        handler = _make_handler(event_bus=bus)

        downstream = [
            PositionChanged(
                event_type=PositionEventType.POSITION_CHANGED,
                data=PositionChangedData(
                    portfolio_id=_PORT_ID,
                    instrument_id="AAPL",
                    quantity=Decimal("100"),
                    avg_cost=Decimal("150.00"),
                    cost_basis=Decimal("15000.00"),
                    currency="USD",
                ),
            ),
        ]

        ctx = MagicMock()
        ctx.fund_slug = "alpha"
        ctx.actor_id = "trader-1"
        ctx.actor_type = MagicMock()
        ctx.actor_type.value = "user"

        with patch.object(handler, "_apply_trade", new_callable=AsyncMock, return_value=downstream):
            await handler.handle_trade(
                request_context=ctx,
                portfolio_id=_PORT_ID,
                instrument_id="AAPL",
                side=TradeSide.BUY,
                quantity=Decimal("100"),
                price=Decimal("150.00"),
            )

        trade_events = cap.get_by_topic("trades.executed")
        assert len(trade_events) == 1
        assert trade_events[0].data["instrument_id"] == "AAPL"

        pos_events = cap.get_by_topic("positions.changed")
        assert len(pos_events) == 1

    async def test_idempotent_duplicate_skips_publish(self) -> None:
        """When _apply_trade returns None, nothing is published."""
        bus = InProcessEventBus()
        cap = EventCapture()
        cap.wire_to_bus(bus, [fund_topic("alpha", "trades.executed")])

        handler = _make_handler(event_bus=bus)
        ctx = MagicMock()
        ctx.fund_slug = "alpha"
        ctx.actor_id = "trader-1"
        ctx.actor_type = MagicMock()
        ctx.actor_type.value = "user"

        with patch.object(handler, "_apply_trade", new_callable=AsyncMock, return_value=None):
            await handler.handle_trade(
                request_context=ctx,
                portfolio_id=_PORT_ID,
                instrument_id="AAPL",
                side=TradeSide.BUY,
                quantity=Decimal("100"),
                price=Decimal("150.00"),
            )

        assert len(cap.events) == 0

    async def test_sell_side_publishes_trade_sell_event_type(self) -> None:
        """SELL trades publish event_type=TRADE_SELL on trades.executed."""
        bus = InProcessEventBus()
        cap = EventCapture()
        cap.wire_to_bus(bus, [fund_topic("alpha", "trades.executed")])

        handler = _make_handler(event_bus=bus)

        ctx = MagicMock()
        ctx.fund_slug = "alpha"
        ctx.actor_id = "trader-1"
        ctx.actor_type = MagicMock()
        ctx.actor_type.value = "user"

        with patch.object(handler, "_apply_trade", new_callable=AsyncMock, return_value=[]):
            await handler.handle_trade(
                request_context=ctx,
                portfolio_id=_PORT_ID,
                instrument_id="AAPL",
                side=TradeSide.SELL,
                quantity=Decimal("50"),
                price=Decimal("160.00"),
            )

        trade_events = cap.get_by_topic("trades.executed")
        assert len(trade_events) == 1
        assert trade_events[0].event_type == PositionEventType.TRADE_SELL

    async def test_no_fund_slug_uses_bare_topic(self) -> None:
        """When fund_slug is empty/None, uses bare 'trades.executed' topic."""
        bus = InProcessEventBus()
        cap = EventCapture()
        cap.wire_to_bus(bus, ["trades.executed"])

        handler = _make_handler(event_bus=bus)

        ctx = MagicMock()
        ctx.fund_slug = None
        ctx.actor_id = "trader-1"
        ctx.actor_type = MagicMock()
        ctx.actor_type.value = "user"

        with patch.object(handler, "_apply_trade", new_callable=AsyncMock, return_value=[]):
            await handler.handle_trade(
                request_context=ctx,
                portfolio_id=_PORT_ID,
                instrument_id="AAPL",
                side=TradeSide.BUY,
                quantity=Decimal("100"),
                price=Decimal("150.00"),
            )

        trade_events = cap.get_by_topic("trades.executed")
        assert len(trade_events) == 1


# ---------------------------------------------------------------------------
# Tests: _publish_downstream
# ---------------------------------------------------------------------------


class TestPublishDownstream:
    async def test_publishes_position_changed(self) -> None:
        bus = InProcessEventBus()
        cap = EventCapture()
        cap.wire_to_bus(bus, [fund_topic("alpha", "positions.changed")])

        handler = _make_handler(event_bus=bus)
        downstream = [
            PositionChanged(
                event_type=PositionEventType.POSITION_CHANGED,
                data=PositionChangedData(
                    portfolio_id=_PORT_ID,
                    instrument_id="AAPL",
                    quantity=Decimal("100"),
                    avg_cost=Decimal("150"),
                    cost_basis=Decimal("15000"),
                    currency="USD",
                ),
            ),
        ]

        await handler._publish_downstream("alpha", "actor-1", "user", downstream)

        events = cap.get_by_topic("positions.changed")
        assert len(events) == 1
        assert events[0].data["instrument_id"] == "AAPL"

    async def test_publishes_pnl_realized(self) -> None:
        bus = InProcessEventBus()
        cap = EventCapture()
        cap.wire_to_bus(bus, [fund_topic("alpha", "pnl.updated")])

        handler = _make_handler(event_bus=bus)
        downstream = [
            PnLRealized(
                event_type=PositionEventType.PNL_REALIZED,
                data=PnLRealizedData(
                    portfolio_id=_PORT_ID,
                    instrument_id="AAPL",
                    realized_pnl=Decimal("500"),
                    price=Decimal("160"),
                    currency="USD",
                ),
            ),
        ]

        await handler._publish_downstream("alpha", "actor-1", "user", downstream)

        events = cap.get_by_topic("pnl.updated")
        assert len(events) == 1

    async def test_publishes_pnl_mark_to_market(self) -> None:
        bus = InProcessEventBus()
        cap = EventCapture()
        cap.wire_to_bus(bus, [fund_topic("alpha", "pnl.updated")])

        handler = _make_handler(event_bus=bus)
        downstream = [
            PnLMarkToMarket(
                event_type=PositionEventType.PNL_MARK_TO_MARKET,
                data=PnLMarkToMarketData(
                    portfolio_id=_PORT_ID,
                    instrument_id="AAPL",
                    market_price=Decimal("200"),
                    market_value=Decimal("20000"),
                    unrealized_pnl=Decimal("5000"),
                    pnl_change=Decimal("500"),
                    currency="USD",
                ),
            ),
        ]

        await handler._publish_downstream("alpha", "actor-1", "user", downstream)

        events = cap.get_by_topic("pnl.updated")
        assert len(events) == 1

    async def test_bare_topic_when_no_fund_slug(self) -> None:
        bus = InProcessEventBus()
        cap = EventCapture()
        cap.wire_to_bus(bus, ["positions.changed"])

        handler = _make_handler(event_bus=bus)
        downstream = [
            PositionChanged(
                event_type=PositionEventType.POSITION_CHANGED,
                data=PositionChangedData(
                    portfolio_id=_PORT_ID,
                    instrument_id="AAPL",
                    quantity=Decimal("100"),
                    avg_cost=Decimal("150"),
                    cost_basis=Decimal("15000"),
                    currency="USD",
                ),
            ),
        ]

        await handler._publish_downstream(None, "actor-1", "user", downstream)

        events = cap.get_by_topic("positions.changed")
        assert len(events) == 1

    async def test_unknown_downstream_event_raises(self) -> None:
        """Unknown downstream event type raises ValueError."""
        handler = _make_handler()

        class UnknownEvent:
            pass

        with pytest.raises(ValueError, match="Unknown downstream event type"):
            await handler._publish_downstream("alpha", "a", "u", [UnknownEvent()])


# ---------------------------------------------------------------------------
# Tests: handle_trade_event — corporate action path
# ---------------------------------------------------------------------------


class TestHandleTradeEventCorporateAction:
    async def test_corporate_action_event_routes_correctly(self) -> None:
        """Events with source=corporate_action route to _apply_corporate_action."""
        bus = InProcessEventBus()
        cap = EventCapture()
        cap.wire_to_bus(bus, [fund_topic("alpha", "positions.changed")])

        sf = _make_session_factory()
        handler = _make_handler(event_bus=bus, session_factory=sf)

        downstream = [
            PositionChanged(
                event_type=PositionEventType.POSITION_CHANGED,
                data=PositionChangedData(
                    portfolio_id=_PORT_ID,
                    instrument_id="AAPL",
                    quantity=Decimal("200"),
                    avg_cost=Decimal("75"),
                    cost_basis=Decimal("15000"),
                    currency="USD",
                ),
            ),
        ]

        with patch.object(
            handler, "_apply_corporate_action", new_callable=AsyncMock, return_value=downstream
        ):
            event = make_trades_executed_event(fund_slug="alpha")
            event = event.model_copy(
                update={
                    "event_type": "corporate_action.split",
                    "data": {
                        "portfolio_id": str(_PORT_ID),
                        "instrument_id": "AAPL",
                        "source": "corporate_action",
                        "quantity": "2",
                    },
                }
            )
            await handler.handle_trade_event(event)

        pos_events = cap.get_by_topic("positions.changed")
        assert len(pos_events) == 1

    async def test_no_fund_slug_is_noop(self) -> None:
        """Events with no fund_slug are silently ignored."""
        handler = _make_handler()

        event = make_trades_executed_event(fund_slug="alpha")
        event = event.model_copy(update={"fund_slug": None})

        # Should not raise
        await handler.handle_trade_event(event)
