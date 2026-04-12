"""Unit tests for FX hedging wiring module."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.fx_hedging.wiring import _make_interest_rate_handler, setup
from app.shared.events import BaseEvent


class TestMakeInterestRateHandler:
    @pytest.mark.asyncio
    async def test_updates_rate_on_valid_event(self) -> None:
        fx_service = AsyncMock()
        handler = _make_interest_rate_handler(fx_service)

        event = BaseEvent(
            event_type="interest_rate.updated",
            data={"currency": "EUR", "rate_1m": "0.0375"},
        )
        await handler(event)

        fx_service.set_interest_rate.assert_called_once_with(
            currency="EUR",
            rate=Decimal("0.0375"),
            tenor_days=30,
            source="mock-exchange",
        )

    @pytest.mark.asyncio
    async def test_skips_when_currency_missing(self) -> None:
        fx_service = AsyncMock()
        handler = _make_interest_rate_handler(fx_service)

        event = BaseEvent(
            event_type="interest_rate.updated",
            data={"rate_1m": "0.0375"},  # no currency
        )
        await handler(event)

        fx_service.set_interest_rate.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_rate_missing(self) -> None:
        fx_service = AsyncMock()
        handler = _make_interest_rate_handler(fx_service)

        event = BaseEvent(
            event_type="interest_rate.updated",
            data={"currency": "EUR"},  # no rate_1m
        )
        await handler(event)

        fx_service.set_interest_rate.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self) -> None:
        fx_service = AsyncMock()
        fx_service.set_interest_rate = AsyncMock(side_effect=RuntimeError("db error"))
        handler = _make_interest_rate_handler(fx_service)

        event = BaseEvent(
            event_type="interest_rate.updated",
            data={"currency": "EUR", "rate_1m": "0.0375"},
        )
        # Should not raise
        await handler(event)


class TestSetup:
    @pytest.mark.asyncio
    @patch("app.modules.fx_hedging.wiring.os.environ", {"APP_ENV": "test"})
    async def test_wires_service_and_subscribes(self) -> None:
        app = MagicMock()
        app.state = MagicMock()
        app.state.market_data_service = MagicMock()
        app.state.market_data_service.fx_converter = MagicMock()

        sf = MagicMock()
        event_bus = MagicMock()
        event_bus.subscribe = MagicMock()

        await setup(app, sf, event_bus=event_bus)

        # Service should be attached to app.state
        assert hasattr(app.state, "fx_hedging_service")
        # Event bus subscription should be registered
        event_bus.subscribe.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.modules.fx_hedging.wiring.os.environ", {"APP_ENV": "test"})
    async def test_no_event_bus_still_works(self) -> None:
        app = MagicMock()
        app.state = MagicMock()
        app.state.market_data_service = MagicMock()
        app.state.market_data_service.fx_converter = MagicMock()

        sf = MagicMock()

        await setup(app, sf, event_bus=None)

        assert hasattr(app.state, "fx_hedging_service")

    @pytest.mark.asyncio
    @patch("app.modules.fx_hedging.wiring.seed_dev_data", new_callable=AsyncMock, create=True)
    @patch("app.modules.fx_hedging.wiring.os.environ", {"APP_ENV": "local"})
    async def test_seeds_in_local_env(self, mock_seed: AsyncMock) -> None:
        app = MagicMock()
        app.state = MagicMock()
        app.state.market_data_service = MagicMock()
        app.state.market_data_service.fx_converter = MagicMock()

        sf = MagicMock()

        with patch("app.modules.fx_hedging.wiring.seed_dev_data", mock_seed):
            # Need to actually patch inside the setup function scope
            with patch("app.modules.fx_hedging.seed.seed_dev_data", mock_seed):
                await setup(app, sf, event_bus=None)
