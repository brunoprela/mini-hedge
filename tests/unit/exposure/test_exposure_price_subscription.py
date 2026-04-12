"""Unit tests for exposure recalculation on price changes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.shared.events import BaseEvent


class TestExposurePriceSubscription:
    """Test that the exposure module subscribes to prices.normalized."""

    @pytest.mark.asyncio
    async def test_subscribes_to_prices_normalized(self) -> None:
        """Verify wiring subscribes to shared prices.normalized topic."""
        from app.modules.exposure.wiring import setup

        app = MagicMock()
        app.state.position_service = MagicMock()
        app.state.security_master_service = MagicMock()
        app.state.market_data_service = MagicMock()
        app.state.market_data_service.fx_converter = MagicMock()
        app.state.portfolio_repo = MagicMock()

        sf = MagicMock()
        mock_bus = MagicMock()
        mock_bus.subscribe = MagicMock()

        mock_fund = MagicMock()
        mock_fund.slug = "test-fund"
        mock_fund.id = "fund-id-1"

        fund_repo = AsyncMock()
        fund_repo.get_all_active = AsyncMock(return_value=[mock_fund])

        with patch(
            "app.modules.exposure.wiring.ExposureRepository"
        ), patch(
            "app.modules.exposure.wiring.ExposureService"
        ):
            await setup(app, sf, event_bus=mock_bus, fund_repo=fund_repo)

        # Should subscribe to both position changes and price changes
        subscribed_topics = [
            call.args[0] for call in mock_bus.subscribe.call_args_list
        ]
        price_topics = [t for t in subscribed_topics if "prices.normalized" in t]
        assert len(price_topics) == 1, (
            f"Expected one prices.normalized subscription, got {subscribed_topics}"
        )

    @pytest.mark.asyncio
    async def test_price_handler_triggers_snapshot_for_all_portfolios(self) -> None:
        """Verify the price handler recalculates exposure for all portfolios."""
        from app.modules.exposure.wiring import setup

        app = MagicMock()
        app.state.position_service = MagicMock()
        app.state.security_master_service = MagicMock()
        app.state.market_data_service = MagicMock()
        app.state.market_data_service.fx_converter = MagicMock()

        mock_portfolio = MagicMock()
        mock_portfolio.id = "00000000-0000-0000-0000-000000000001"
        portfolio_repo = AsyncMock()
        portfolio_repo.get_by_fund = AsyncMock(return_value=[mock_portfolio])
        app.state.portfolio_repo = portfolio_repo

        sf = MagicMock()
        mock_bus = MagicMock()

        mock_fund = MagicMock()
        mock_fund.slug = "test-fund"
        mock_fund.id = "fund-id-1"
        fund_repo = AsyncMock()
        fund_repo.get_all_active = AsyncMock(return_value=[mock_fund])

        mock_exposure_service = MagicMock()
        mock_exposure_service.take_snapshot = AsyncMock()

        handlers: dict[str, list] = {}

        def capture_subscribe(topic, handler):
            handlers.setdefault(topic, []).append(handler)

        mock_bus.subscribe = capture_subscribe

        with patch(
            "app.modules.exposure.wiring.ExposureRepository"
        ), patch(
            "app.modules.exposure.wiring.ExposureService",
            return_value=mock_exposure_service,
        ):
            await setup(app, sf, event_bus=mock_bus, fund_repo=fund_repo)

        # Find the prices.normalized handler
        price_handlers = []
        for topic, hs in handlers.items():
            if "prices.normalized" in topic:
                price_handlers.extend(hs)
        assert len(price_handlers) == 1

        # Call the handler
        event = BaseEvent(
            event_type="prices.normalized",
            data={"instrument_id": "AAPL"},
        )
        await price_handlers[0](event)

        mock_exposure_service.take_snapshot.assert_called_once()
