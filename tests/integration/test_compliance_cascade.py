"""Compliance cascade integration test — pre-trade gate → orders → positions.

Demonstrates the end-to-end cascade from a PM submitting an order, through
the pre-trade compliance gate, into order state and (when approved) into
positions via the broker → trades.executed → TradeHandler pipeline.

One focused scenario: a SHORT_SELLING rule (``allow_short=False``) blocks
a sell that would create a short position while allowing a buy to fill
normally. Verifies:

- Compliant order is approved, filled, and produces a position.
- Violating order is rejected at the pre-trade gate.
- The rejected order creates no position and emits a ``trades.rejected``
  compliance decision event.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest

from app.modules.compliance.interfaces import RuleType, Severity
from app.modules.orders.interfaces import (
    CreateOrderRequest,
    OrderSide,
    OrderState,
    OrderType,
)
from app.modules.platform.seed import FUND_ALPHA_ID
from app.shared.auth.request_context import ActorType, RequestContext, set_request_context
from app.shared.schema_registry import fund_topic
from tests.integration.conftest import ALPHA_PORTFOLIO_ID, WiredSystem


@pytest.mark.integration
class TestComplianceCascade:
    """Pre-trade compliance gate → orders → positions cascade."""

    async def test_pre_trade_compliance_rejects_oversized_order(
        self,
        wired_system: WiredSystem,
    ) -> None:
        """Pre-trade compliance blocks a short-creating sell, approves the buy.

        Setup: A SHORT_SELLING rule on fund-alpha with ``allow_short=False``.

        Flow:
          1. Submit a BUY of 10 shares — no short position created → approved,
             fills via the StubBroker, produces a position.
          2. Submit a SELL of 100 shares on an instrument with no prior long
             position — would create a short of -100 → rejected at the gate.

        Assertions:
          - Approved order ends in FILLED; a position is created.
          - Rejected order ends in REJECTED with ``rejection_reason`` set,
            no position is created, and no ``trades.executed`` event fires
            for the rejected instrument.
          - A ``trades.rejected`` compliance decision event is emitted.
        """
        ws = wired_system

        # Ensure we're acting as fund-alpha admin (matches autouse default,
        # but re-set so the context is explicit for this test).
        ctx = RequestContext(
            actor_id="test-pm",
            actor_type=ActorType.USER,
            fund_slug="alpha",
            fund_id=FUND_ALPHA_ID,
            roles=frozenset({"admin"}),
            permissions=frozenset(),
        )
        set_request_context(ctx)

        # Capture the compliance decision topic — the default wired_system
        # capture doesn't subscribe to orders lifecycle decision topics.
        ws.capture.wire_to_bus(
            ws.event_bus,
            [fund_topic("alpha", "trades.rejected")],
        )

        # --- 1. Seed the compliance rule (fund-scoped) ----------------------
        async with ws.session_factory.fund_scope("alpha"):
            rule = await ws.compliance_service.create_rule(
                name="no-naked-shorts",
                rule_type=RuleType.SHORT_SELLING,
                severity=Severity.BLOCK,
                parameters={"allow_short": False},
                actor_id="test-pm",
            )
            assert rule.is_active

        portfolio_id = UUID(ALPHA_PORTFOLIO_ID)
        ws.capture.clear()

        # --- 2. Approved path: small buy — no short created → fills ---------
        approved_request = CreateOrderRequest(
            portfolio_id=portfolio_id,
            instrument_id="TSLA",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("10"),
            limit_price=Decimal("250.00"),
        )
        async with ws.session_factory.fund_scope("alpha"):
            approved = await ws.order_service.create_order(
                approved_request, fund_slug="alpha", actor_id="test-pm"
            )
        assert approved.state == OrderState.FILLED, (
            f"Expected FILLED, got {approved.state}: {approved.rejection_reason}"
        )

        # Position was created via trades.executed → TradeHandler.
        async with ws.session_factory.fund_scope("alpha"):
            positions = await ws.position_service.get_by_portfolio(portfolio_id)
        tsla = [p for p in positions if p.instrument_id == "TSLA"]
        assert len(tsla) == 1
        assert tsla[0].quantity == Decimal("10")

        ws.capture.clear()

        # --- 3. Rejected path: sell with no long → would create short ------
        rejected_request = CreateOrderRequest(
            portfolio_id=portfolio_id,
            # Unique ticker to ensure no prior long from other tests.
            instrument_id="SHOP",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("100"),
            limit_price=Decimal("75.00"),
        )
        async with ws.session_factory.fund_scope("alpha"):
            rejected = await ws.order_service.create_order(
                rejected_request, fund_slug="alpha", actor_id="test-pm"
            )

        # Order must terminate in REJECTED with a reason mentioning the rule.
        assert rejected.state == OrderState.REJECTED, (
            f"Expected REJECTED, got {rejected.state}"
        )
        assert rejected.rejection_reason is not None
        assert "no-naked-shorts" in rejected.rejection_reason

        # No position should have been created for the rejected instrument.
        async with ws.session_factory.fund_scope("alpha"):
            positions_after = await ws.position_service.get_by_portfolio(portfolio_id)
        shop = [p for p in positions_after if p.instrument_id == "SHOP"]
        assert len(shop) == 0, "Rejected order must not produce a position"

        # No trades.executed event should have fired for the rejected order.
        executed = [
            e
            for e in ws.capture.get_by_topic("trades.executed")
            if e.data.get("instrument_id") == "SHOP"
        ]
        assert executed == [], "Rejected order must not emit trades.executed"

        # A trades.rejected compliance decision event must have been emitted.
        rejected_events = ws.capture.get_by_topic("trades.rejected")
        assert len(rejected_events) >= 1, (
            f"Expected trades.rejected, got topics: {ws.capture.topics()}"
        )
        assert any(
            e.data.get("instrument_id") == "SHOP" for e in rejected_events
        ), "Expected a trades.rejected event for the SHOP order"

        # Sanity: trade_id on the decision event should match the rejected order.
        rejected_for_shop = next(
            e for e in rejected_events if e.data.get("instrument_id") == "SHOP"
        )
        assert rejected_for_shop.data.get("trade_id") == str(rejected.id)
