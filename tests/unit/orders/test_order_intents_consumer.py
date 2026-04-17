"""Unit tests for order-intents.generated Kafka consumer in orders wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.shared.events import BaseEvent


# The orders wiring setup() imports many things inside the function body.
# We patch at module level where those classes are defined.
_PATCHES = [
    "app.modules.orders.core.algo_engine.AlgoEngine",
    "app.modules.orders.core.best_execution.BestExecutionService",
    "app.modules.orders.repositories.AllocationRepository",
    "app.modules.orders.repositories.RoutingRepository",
    "app.modules.orders.repositories.ScorecardRepository",
    "app.modules.orders.services.ScorecardService",
    "app.modules.orders.services.AllocationService",
]


def _apply_patches():
    """Return a list of started patchers."""
    patchers = [patch(p) for p in _PATCHES]
    for p in patchers:
        p.start()
    return patchers


def _stop_patches(patchers):
    for p in patchers:
        p.stop()


def _make_app():
    app = MagicMock()
    app.state.compliance_service = MagicMock()
    app.state.compliance_service.pre_trade_gate = MagicMock()
    app.state.audit_repo = MagicMock()
    app.state.market_data_service = MagicMock()
    return app


class TestOrderIntentsConsumer:
    """Test that orders module subscribes to order_intents.generated and creates orders."""

    @pytest.mark.asyncio
    async def test_subscribes_to_order_intents_for_active_funds(self) -> None:
        from app.modules.orders.wiring import setup

        app = _make_app()
        sf = MagicMock()
        mock_bus = MagicMock()
        mock_bus.subscribe = MagicMock()

        mock_fund = MagicMock()
        mock_fund.slug = "test-fund"
        fund_repo = AsyncMock()
        fund_repo.list_active = AsyncMock(return_value=[mock_fund])

        patchers = _apply_patches()
        try:
            await setup(app, sf, event_bus=mock_bus, fund_repo=fund_repo)
        finally:
            _stop_patches(patchers)

        subscribed_topics = [
            call.args[0] for call in mock_bus.subscribe.call_args_list
        ]
        intent_topics = [t for t in subscribed_topics if "order_intents.generated" in t]
        assert len(intent_topics) == 1

    @pytest.mark.asyncio
    async def test_handler_creates_orders_from_intents(self) -> None:
        from app.modules.orders.wiring import setup

        app = _make_app()
        sf = MagicMock()
        mock_bus = MagicMock()
        handlers: dict[str, list] = {}

        def capture_subscribe(topic, handler):
            handlers.setdefault(topic, []).append(handler)

        mock_bus.subscribe = capture_subscribe

        mock_fund = MagicMock()
        mock_fund.slug = "test-fund"
        fund_repo = AsyncMock()
        fund_repo.list_active = AsyncMock(return_value=[mock_fund])

        mock_order_service = MagicMock()
        mock_order_service.create_order = AsyncMock()

        patchers = _apply_patches()
        patchers.append(patch(
            "app.modules.orders.wiring.OrderService",
            return_value=mock_order_service,
        ))
        patchers[-1].start()
        try:
            await setup(app, sf, event_bus=mock_bus, fund_repo=fund_repo)
        finally:
            _stop_patches(patchers)

        # Find the handler
        intent_handlers = []
        for topic, hs in handlers.items():
            if "order_intents.generated" in topic:
                intent_handlers.extend(hs)
        assert len(intent_handlers) == 1

        # Invoke handler with 2 intents
        event = BaseEvent(
            event_type="order_intents.generated",
            data={
                "portfolio_id": "00000000-0000-0000-0000-000000000001",
                "intents": [
                    {"instrument_id": "AAPL", "side": "buy", "quantity": "100"},
                    {"instrument_id": "MSFT", "side": "sell", "quantity": "50"},
                ],
            },
        )
        await intent_handlers[0](event)

        assert mock_order_service.create_order.call_count == 2
        first_call = mock_order_service.create_order.call_args_list[0]
        request = first_call.args[0]
        assert request.instrument_id == "AAPL"
        assert request.side == "buy"
        assert request.quantity == 100

    @pytest.mark.asyncio
    async def test_handler_skips_when_no_intents(self) -> None:
        from app.modules.orders.wiring import setup

        app = _make_app()
        sf = MagicMock()
        mock_bus = MagicMock()
        handlers: dict[str, list] = {}

        def capture_subscribe(topic, handler):
            handlers.setdefault(topic, []).append(handler)

        mock_bus.subscribe = capture_subscribe

        mock_fund = MagicMock()
        mock_fund.slug = "test-fund"
        fund_repo = AsyncMock()
        fund_repo.list_active = AsyncMock(return_value=[mock_fund])

        mock_order_service = MagicMock()
        mock_order_service.create_order = AsyncMock()

        patchers = _apply_patches()
        patchers.append(patch(
            "app.modules.orders.wiring.OrderService",
            return_value=mock_order_service,
        ))
        patchers[-1].start()
        try:
            await setup(app, sf, event_bus=mock_bus, fund_repo=fund_repo)
        finally:
            _stop_patches(patchers)

        intent_handlers = []
        for topic, hs in handlers.items():
            if "order_intents.generated" in topic:
                intent_handlers.extend(hs)

        event = BaseEvent(
            event_type="order_intents.generated",
            data={
                "portfolio_id": "00000000-0000-0000-0000-000000000001",
                "intents": [],
            },
        )
        await intent_handlers[0](event)
        mock_order_service.create_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_handler_continues_on_individual_intent_failure(self) -> None:
        from app.modules.orders.wiring import setup

        app = _make_app()
        sf = MagicMock()
        mock_bus = MagicMock()
        handlers: dict[str, list] = {}

        def capture_subscribe(topic, handler):
            handlers.setdefault(topic, []).append(handler)

        mock_bus.subscribe = capture_subscribe

        mock_fund = MagicMock()
        mock_fund.slug = "test-fund"
        fund_repo = AsyncMock()
        fund_repo.list_active = AsyncMock(return_value=[mock_fund])

        mock_order_service = MagicMock()
        mock_order_service.create_order = AsyncMock(
            side_effect=[RuntimeError("compliance rejected"), MagicMock()]
        )

        patchers = _apply_patches()
        patchers.append(patch(
            "app.modules.orders.wiring.OrderService",
            return_value=mock_order_service,
        ))
        patchers[-1].start()
        try:
            await setup(app, sf, event_bus=mock_bus, fund_repo=fund_repo)
        finally:
            _stop_patches(patchers)

        intent_handlers = []
        for topic, hs in handlers.items():
            if "order_intents.generated" in topic:
                intent_handlers.extend(hs)

        event = BaseEvent(
            event_type="order_intents.generated",
            data={
                "portfolio_id": "00000000-0000-0000-0000-000000000001",
                "intents": [
                    {"instrument_id": "AAPL", "side": "buy", "quantity": "100"},
                    {"instrument_id": "MSFT", "side": "sell", "quantity": "50"},
                ],
            },
        )
        await intent_handlers[0](event)
        assert mock_order_service.create_order.call_count == 2

    @pytest.mark.asyncio
    async def test_no_subscription_without_fund_repo(self) -> None:
        from app.modules.orders.wiring import setup

        app = _make_app()
        sf = MagicMock()
        mock_bus = MagicMock()
        mock_bus.subscribe = MagicMock()

        patchers = _apply_patches()
        try:
            await setup(app, sf, event_bus=mock_bus, fund_repo=None)
        finally:
            _stop_patches(patchers)

        mock_bus.subscribe.assert_not_called()
