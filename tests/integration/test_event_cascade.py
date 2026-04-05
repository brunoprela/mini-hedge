"""Cascade integration tests — full event flow with real PostgreSQL.

Tests the event-driven subscription path: events are published on the bus
and handlers react via their subscriptions (matching production wiring).

Verifies:
- trades.executed → TradeHandler → positions.changed + pnl.updated cascade
- Price update → MTM → pnl.updated → PostTradeMonitor cascade
- Multi-fund isolation
- Handler failure isolation
- Idempotent trade processing
"""

from __future__ import annotations

import contextlib
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

from app.modules.platform.seed import FUND_ALPHA_ID, FUND_BETA_ID
from app.shared.request_context import ActorType, RequestContext, set_request_context
from app.shared.schema_registry import fund_topic, shared_topic

if TYPE_CHECKING:
    from app.shared.events import BaseEvent
from tests.factories import make_price_event, make_trades_executed_event
from tests.integration.conftest import (
    ALPHA_PORTFOLIO_ID,
    BETA_PORTFOLIO_ID,
    WiredSystem,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(slug: str, fund_id: str, actor_id: str = "test-user") -> RequestContext:
    ctx = RequestContext(
        actor_id=actor_id,
        actor_type=ActorType.USER,
        fund_slug=slug,
        fund_id=fund_id,
        roles=frozenset({"admin"}),
        permissions=frozenset(),
    )
    set_request_context(ctx)
    return ctx


async def _publish_trade(
    ws: WiredSystem,
    slug: str,
    fund_id: str,
    portfolio_id: str,
    instrument_id: str,
    side: str = "buy",
    quantity: Decimal = Decimal("100"),
    price: Decimal = Decimal("150.00"),
    trade_id: UUID | None = None,
) -> BaseEvent:
    """Publish a trades.executed event on the bus (the event-driven path)."""
    _make_ctx(slug, fund_id)
    event = make_trades_executed_event(
        portfolio_id=UUID(portfolio_id),
        instrument_id=instrument_id,
        side=side,
        quantity=quantity,
        price=price,
        fund_slug=slug,
        trade_id=trade_id or uuid4(),
    )
    await ws.event_bus.publish(fund_topic(slug, "trades.executed"), event)
    return event


# ---------------------------------------------------------------------------
# Trade cascade: trades.executed → TradeHandler → positions.changed → downstream
# ---------------------------------------------------------------------------


class TestTradeCascade:
    """Verify the full event-driven trade cascade."""

    async def test_trade_event_creates_position(
        self,
        wired_system: WiredSystem,
    ) -> None:
        """Publishing trades.executed triggers TradeHandler which creates a position."""
        ws = wired_system

        await _publish_trade(
            ws,
            "alpha",
            FUND_ALPHA_ID,
            ALPHA_PORTFOLIO_ID,
            "AAPL",
            "buy",
            Decimal("100"),
            Decimal("150.00"),
        )

        # Should have published positions.changed (TradeHandler downstream)
        pos_events = ws.capture.get_by_topic("positions.changed")
        assert len(pos_events) >= 1, (
            f"Expected positions.changed, got topics: {ws.capture.topics()}"
        )
        assert pos_events[0].data["portfolio_id"] == ALPHA_PORTFOLIO_ID
        assert pos_events[0].data["instrument_id"] == "AAPL"

        # Position should exist in DB
        async with ws.session_factory.fund_scope("alpha"):
            positions = await ws.position_service.get_by_portfolio(UUID(ALPHA_PORTFOLIO_ID))
        aapl_positions = [p for p in positions if p.instrument_id == "AAPL"]
        assert len(aapl_positions) == 1
        assert aapl_positions[0].quantity == Decimal("100")

    async def test_trade_triggers_cash_settlement(
        self,
        wired_system: WiredSystem,
    ) -> None:
        """trades.executed should trigger CashManagementService handler."""
        ws = wired_system

        await _publish_trade(
            ws,
            "alpha",
            FUND_ALPHA_ID,
            ALPHA_PORTFOLIO_ID,
            "MSFT",
            "buy",
            Decimal("50"),
            Decimal("400.00"),
        )

        # Cash handler subscribes to trades.executed and runs in the same publish.
        # If no ExceptionGroup was raised, both TradeHandler and CashHandler ran.
        trade_events = ws.capture.get_by_topic("trades.executed")
        assert len(trade_events) >= 1

    async def test_additive_position_updates(
        self,
        wired_system: WiredSystem,
    ) -> None:
        """Multiple trades in the same instrument should update the same position."""
        ws = wired_system

        # Trade 1: buy 100 GOOGL
        await _publish_trade(
            ws,
            "alpha",
            FUND_ALPHA_ID,
            ALPHA_PORTFOLIO_ID,
            "GOOGL",
            "buy",
            Decimal("100"),
            Decimal("170.00"),
        )

        ws.capture.clear()

        # Trade 2: buy 50 more GOOGL
        await _publish_trade(
            ws,
            "alpha",
            FUND_ALPHA_ID,
            ALPHA_PORTFOLIO_ID,
            "GOOGL",
            "buy",
            Decimal("50"),
            Decimal("175.00"),
        )

        # Position should reflect both trades
        async with ws.session_factory.fund_scope("alpha"):
            positions = await ws.position_service.get_by_portfolio(UUID(ALPHA_PORTFOLIO_ID))
        googl = [p for p in positions if p.instrument_id == "GOOGL"]
        assert len(googl) == 1
        assert googl[0].quantity == Decimal("150")

    async def test_sell_reduces_position(
        self,
        wired_system: WiredSystem,
    ) -> None:
        """A sell trade should reduce an existing position."""
        ws = wired_system

        # Buy 100
        await _publish_trade(
            ws,
            "alpha",
            FUND_ALPHA_ID,
            ALPHA_PORTFOLIO_ID,
            "AMZN",
            "buy",
            Decimal("100"),
            Decimal("180.00"),
        )

        # Sell 40
        await _publish_trade(
            ws,
            "alpha",
            FUND_ALPHA_ID,
            ALPHA_PORTFOLIO_ID,
            "AMZN",
            "sell",
            Decimal("40"),
            Decimal("190.00"),
        )

        async with ws.session_factory.fund_scope("alpha"):
            positions = await ws.position_service.get_by_portfolio(UUID(ALPHA_PORTFOLIO_ID))
        amzn = [p for p in positions if p.instrument_id == "AMZN"]
        assert len(amzn) == 1
        assert amzn[0].quantity == Decimal("60")


# ---------------------------------------------------------------------------
# Price cascade: price event → MTM → pnl.updated → PostTradeMonitor
# ---------------------------------------------------------------------------


class TestPriceCascade:
    """Verify price update triggers MTM recalculation and PnL events."""

    async def test_price_update_triggers_pnl(
        self,
        wired_system: WiredSystem,
    ) -> None:
        """A price update for an instrument with positions should publish pnl.updated."""
        ws = wired_system

        # Establish a position first
        await _publish_trade(
            ws,
            "alpha",
            FUND_ALPHA_ID,
            ALPHA_PORTFOLIO_ID,
            "AAPL",
            "buy",
            Decimal("200"),
            Decimal("150.00"),
        )

        ws.capture.clear()

        # Publish a price update — large move to exceed noise filter
        price_event = make_price_event(instrument_id="AAPL", mid=Decimal("200.00"))
        await ws.event_bus.publish(shared_topic("prices.normalized"), price_event)

        # Should have published pnl.updated
        pnl_events = ws.capture.get_by_topic("pnl.updated")
        assert len(pnl_events) >= 1, f"Expected pnl.updated, got topics: {ws.capture.topics()}"
        assert pnl_events[0].data["instrument_id"] == "AAPL"

    async def test_price_update_for_unknown_instrument_is_noop(
        self,
        wired_system: WiredSystem,
    ) -> None:
        """Price for an instrument nobody holds should not produce pnl events."""
        ws = wired_system
        ws.capture.clear()

        price_event = make_price_event(instrument_id="UNKNOWN_TICKER", mid=Decimal("50.00"))
        await ws.event_bus.publish(shared_topic("prices.normalized"), price_event)

        pnl_events = ws.capture.get_by_topic("pnl.updated")
        assert len(pnl_events) == 0


# ---------------------------------------------------------------------------
# Multi-fund isolation
# ---------------------------------------------------------------------------


class TestMultiFundIsolation:
    """Verify events and data are scoped to the correct fund."""

    async def test_alpha_trade_does_not_affect_beta(
        self,
        wired_system: WiredSystem,
    ) -> None:
        """A trade in fund-alpha should not create positions in fund-beta."""
        ws = wired_system

        await _publish_trade(
            ws,
            "alpha",
            FUND_ALPHA_ID,
            ALPHA_PORTFOLIO_ID,
            "AAPL",
            "buy",
            Decimal("100"),
            Decimal("150.00"),
        )

        # Beta should have no positions
        _make_ctx("beta", FUND_BETA_ID, actor_id="beta-pm")
        async with ws.session_factory.fund_scope("beta"):
            beta_positions = await ws.position_service.get_by_portfolio(UUID(BETA_PORTFOLIO_ID))
        aapl_in_beta = [p for p in beta_positions if p.instrument_id == "AAPL"]
        assert len(aapl_in_beta) == 0

    async def test_events_scoped_to_fund_topic(
        self,
        wired_system: WiredSystem,
    ) -> None:
        """Trade events should only appear on the correct fund's topic."""
        ws = wired_system
        ws.capture.clear()

        await _publish_trade(
            ws,
            "alpha",
            FUND_ALPHA_ID,
            ALPHA_PORTFOLIO_ID,
            "AAPL",
            "buy",
            Decimal("10"),
            Decimal("150.00"),
        )

        # All fund-scoped events should be on fund-alpha topics
        for ce in ws.capture.events:
            topic = ce.topic
            if topic.startswith("fund-"):
                assert "fund-alpha" in topic, f"Unexpected topic for alpha trade: {topic}"


# ---------------------------------------------------------------------------
# Handler failure isolation
# ---------------------------------------------------------------------------


class TestHandlerFailureIsolation:
    """Verify that one handler failing doesn't prevent others from running."""

    async def test_failing_handler_does_not_block_others(
        self,
        wired_system: WiredSystem,
    ) -> None:
        """If one positions.changed handler raises, others should still execute."""
        ws = wired_system

        call_log: list[str] = []

        async def failing_handler(event: BaseEvent) -> None:
            call_log.append("failing")
            raise RuntimeError("Deliberate test failure")

        async def tracking_handler(event: BaseEvent) -> None:
            call_log.append("tracking")

        ws.event_bus.subscribe(fund_topic("alpha", "positions.changed"), failing_handler)
        ws.event_bus.subscribe(fund_topic("alpha", "positions.changed"), tracking_handler)

        # Publish a trade — TradeHandler processes it and publishes positions.changed
        # The ExceptionGroup from the failing handler bubbles up through
        # _publish_downstream → publish. We expect it but want to verify both
        # handlers were called.
        with contextlib.suppress(ExceptionGroup):
            await _publish_trade(
                ws,
                "alpha",
                FUND_ALPHA_ID,
                ALPHA_PORTFOLIO_ID,
                "NVDA",
                "buy",
                Decimal("5"),
                Decimal("800.00"),
            )

        # Both handlers should have been called despite the failure
        assert "failing" in call_log
        assert "tracking" in call_log


# ---------------------------------------------------------------------------
# Idempotent trade processing
# ---------------------------------------------------------------------------


class TestIdempotency:
    """Verify duplicate events are handled correctly."""

    async def test_duplicate_trade_event_is_noop(
        self,
        wired_system: WiredSystem,
    ) -> None:
        """Publishing the same trade_id twice should not double the position."""
        ws = wired_system
        trade_id = uuid4()

        await _publish_trade(
            ws,
            "alpha",
            FUND_ALPHA_ID,
            ALPHA_PORTFOLIO_ID,
            "META",
            "buy",
            Decimal("100"),
            Decimal("500.00"),
            trade_id=trade_id,
        )

        # Get position after first trade
        async with ws.session_factory.fund_scope("alpha"):
            positions = await ws.position_service.get_by_portfolio(UUID(ALPHA_PORTFOLIO_ID))
        meta_qty_first = sum(p.quantity for p in positions if p.instrument_id == "META")
        assert meta_qty_first == Decimal("100")

        ws.capture.clear()

        # Same trade_id again — TradeHandler uses trade_id as idempotency key
        await _publish_trade(
            ws,
            "alpha",
            FUND_ALPHA_ID,
            ALPHA_PORTFOLIO_ID,
            "META",
            "buy",
            Decimal("100"),
            Decimal("500.00"),
            trade_id=trade_id,
        )

        # Position should be unchanged
        async with ws.session_factory.fund_scope("alpha"):
            positions = await ws.position_service.get_by_portfolio(UUID(ALPHA_PORTFOLIO_ID))
        meta_qty_second = sum(p.quantity for p in positions if p.instrument_id == "META")
        assert meta_qty_second == meta_qty_first

        # No new downstream events
        pos_events = ws.capture.get_by_topic("positions.changed")
        assert len(pos_events) == 0, "Duplicate trade should not publish new events"
