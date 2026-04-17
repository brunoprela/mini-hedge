"""Unit tests for corporate-actions.announced Kafka consumer in positions wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.shared.events import BaseEvent


class TestCorporateActionConsumer:
    """Verify positions module subscribes to corporate-actions.announced."""

    @pytest.mark.asyncio
    async def test_subscribes_to_corporate_actions_announced(self) -> None:
        from app.modules.positions.wiring import setup

        app = MagicMock()
        sf = MagicMock()
        sf.fund_scope = MagicMock()

        mock_bus = MagicMock()
        mock_bus.subscribe = MagicMock()

        mock_fund = MagicMock()
        mock_fund.slug = "test-fund"
        fund_repo = AsyncMock()
        fund_repo.list_active = AsyncMock(return_value=[mock_fund])

        sm_service = MagicMock()

        with patch("app.modules.positions.wiring.EventStoreRepository"), \
             patch("app.modules.positions.wiring.CurrentPositionRepository"), \
             patch("app.modules.positions.wiring.LotRepository"), \
             patch("app.modules.positions.wiring.DailyPnLRepository"), \
             patch("app.modules.positions.wiring.PositionProjector"), \
             patch("app.modules.positions.wiring.TradeHandler"), \
             patch("app.modules.positions.wiring.MarkToMarketHandler"), \
             patch("app.modules.positions.wiring.PositionService"):
            await setup(
                app, sf,
                event_bus=mock_bus,
                fund_repo=fund_repo,
                security_master_service=sm_service,
            )

        subscribed_topics = [
            call.args[0] for call in mock_bus.subscribe.call_args_list
        ]
        ca_topics = [t for t in subscribed_topics if "corporate-actions.announced" in t]
        assert len(ca_topics) == 1

    @pytest.mark.asyncio
    async def test_handler_fans_out_to_portfolios(self) -> None:
        from app.modules.positions.wiring import setup

        app = MagicMock()
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

        # Mock position repo to return positions holding the instrument
        mock_position = MagicMock()
        mock_position.portfolio_id = "00000000-0000-0000-0000-000000000001"
        mock_position_repo = MagicMock()
        mock_position_repo.get_by_instrument = AsyncMock(return_value=[mock_position])

        mock_trade_handler = MagicMock()
        mock_trade_handler.handle_trade_event = AsyncMock()

        # Use a real async context manager for fund_scope
        class _FundScope:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        sf.fund_scope = MagicMock(return_value=_FundScope())

        with patch("app.modules.positions.wiring.EventStoreRepository"), \
             patch("app.modules.positions.wiring.CurrentPositionRepository", return_value=mock_position_repo), \
             patch("app.modules.positions.wiring.LotRepository"), \
             patch("app.modules.positions.wiring.DailyPnLRepository"), \
             patch("app.modules.positions.wiring.PositionProjector"), \
             patch("app.modules.positions.wiring.TradeHandler", return_value=mock_trade_handler), \
             patch("app.modules.positions.wiring.MarkToMarketHandler"), \
             patch("app.modules.positions.wiring.PositionService"):
            await setup(
                app, sf,
                event_bus=mock_bus,
                fund_repo=fund_repo,
                security_master_service=MagicMock(),
            )

        # Find the corporate actions handler
        ca_handlers = []
        for topic, hs in handlers.items():
            if "corporate-actions.announced" in topic:
                ca_handlers.extend(hs)
        assert len(ca_handlers) == 1

        # Fire a stock split event
        event = BaseEvent(
            event_type="corporate_action.announced",
            data={
                "instrument_id": "AAPL",
                "action_type": "stock_split",
                "action_id": "00000000-0000-0000-0000-000000000099",
                "ratio": "4",
                "currency": "USD",
            },
        )
        await ca_handlers[0](event)

        # Should have called handle_trade_event once (one portfolio holds AAPL)
        mock_trade_handler.handle_trade_event.assert_called_once()
        call_event = mock_trade_handler.handle_trade_event.call_args[0][0]
        assert call_event.data["source"] == "corporate_action"
        assert call_event.data["instrument_id"] == "AAPL"
        assert call_event.fund_slug == "test-fund"

    @pytest.mark.asyncio
    async def test_handler_skips_when_no_instrument_id(self) -> None:
        from app.modules.positions.wiring import setup

        app = MagicMock()
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

        mock_position_repo = MagicMock()
        mock_position_repo.get_by_instrument = AsyncMock(return_value=[])

        mock_trade_handler = MagicMock()
        mock_trade_handler.handle_trade_event = AsyncMock()

        with patch("app.modules.positions.wiring.EventStoreRepository"), \
             patch("app.modules.positions.wiring.CurrentPositionRepository", return_value=mock_position_repo), \
             patch("app.modules.positions.wiring.LotRepository"), \
             patch("app.modules.positions.wiring.DailyPnLRepository"), \
             patch("app.modules.positions.wiring.PositionProjector"), \
             patch("app.modules.positions.wiring.TradeHandler", return_value=mock_trade_handler), \
             patch("app.modules.positions.wiring.MarkToMarketHandler"), \
             patch("app.modules.positions.wiring.PositionService"):
            await setup(
                app, sf,
                event_bus=mock_bus,
                fund_repo=fund_repo,
                security_master_service=MagicMock(),
            )

        ca_handlers = []
        for topic, hs in handlers.items():
            if "corporate-actions.announced" in topic:
                ca_handlers.extend(hs)

        # Event with missing instrument_id — should return early
        event = BaseEvent(
            event_type="corporate_action.announced",
            data={"action_type": "stock_split"},
        )
        await ca_handlers[0](event)
        mock_trade_handler.handle_trade_event.assert_not_called()
