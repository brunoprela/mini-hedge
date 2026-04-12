"""Unit tests for risk engine module wiring — setup function."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.risk_engine.wiring import setup


def _make_app_and_sf():
    """Build mock FastAPI app and session factory for wiring tests."""
    app = MagicMock()
    app.state = MagicMock()
    app.state.position_service = MagicMock()
    app.state.market_data_service = MagicMock()
    app.state.market_data_service.fx_converter = MagicMock()
    app.state.security_master_service = MagicMock()
    app.state.fund_repo = AsyncMock()
    app.state.fund_repo.get_all_active = AsyncMock(return_value=[])

    sf = MagicMock()
    return app, sf


class TestSetupWiring:
    async def test_services_attached_to_app_state(self) -> None:
        app, sf = _make_app_and_sf()

        await setup(app, sf)

        assert hasattr(app.state, "risk_snapshot_service")
        assert hasattr(app.state, "counterparty_risk_service")
        assert hasattr(app.state, "liquidity_margin_service")

    async def test_services_wired_without_event_bus(self) -> None:
        app, sf = _make_app_and_sf()

        await setup(app, sf, event_bus=None)

        # Should not raise, services still wired
        assert hasattr(app.state, "risk_snapshot_service")

    async def test_event_bus_subscriptions_created(self) -> None:
        app, sf = _make_app_and_sf()

        fund = MagicMock()
        fund.slug = "alpha"
        fund.id = str(uuid4())
        app.state.fund_repo.get_all_active.return_value = [fund]

        event_bus = MagicMock()
        event_bus.subscribe = MagicMock()

        await setup(app, sf, event_bus=event_bus)

        # Should subscribe to positions.changed for each fund
        event_bus.subscribe.assert_called_once()
        topic = event_bus.subscribe.call_args[0][0]
        assert "positions.changed" in topic

    async def test_multiple_funds_get_subscriptions(self) -> None:
        app, sf = _make_app_and_sf()

        fund1 = MagicMock()
        fund1.slug = "alpha"
        fund1.id = str(uuid4())
        fund2 = MagicMock()
        fund2.slug = "beta"
        fund2.id = str(uuid4())
        app.state.fund_repo.get_all_active.return_value = [fund1, fund2]

        event_bus = MagicMock()
        event_bus.subscribe = MagicMock()

        await setup(app, sf, event_bus=event_bus)

        assert event_bus.subscribe.call_count == 2

    @patch.dict("os.environ", {"APP_ENV": "local"})
    @patch("app.modules.risk_engine.wiring.logger")
    async def test_seed_called_in_local_env(self, mock_logger) -> None:
        app, sf = _make_app_and_sf()

        with patch("app.modules.risk_engine.seed.seed_dev_data", new_callable=AsyncMock) as mock_seed:
            await setup(app, sf)
            mock_seed.assert_called_once_with(app, sf)

    @patch.dict("os.environ", {"APP_ENV": "production"})
    async def test_seed_skipped_in_production(self) -> None:
        app, sf = _make_app_and_sf()

        with patch("app.modules.risk_engine.seed.seed_dev_data", new_callable=AsyncMock) as mock_seed:
            await setup(app, sf)
            mock_seed.assert_not_called()

    @patch.dict("os.environ", {"APP_ENV": "local"})
    async def test_seed_failure_does_not_crash(self) -> None:
        app, sf = _make_app_and_sf()

        with patch(
            "app.modules.risk_engine.seed.seed_dev_data",
            new_callable=AsyncMock,
            side_effect=Exception("seed failed"),
        ):
            # Should not raise
            await setup(app, sf)


class TestEventHandler:
    async def test_handler_calls_take_snapshot(self) -> None:
        app, sf = _make_app_and_sf()

        fund = MagicMock()
        fund.slug = "alpha"
        fund.id = str(uuid4())
        app.state.fund_repo.get_all_active.return_value = [fund]

        event_bus = MagicMock()
        captured_handler = None

        def capture_subscribe(topic, handler):
            nonlocal captured_handler
            captured_handler = handler

        event_bus.subscribe = capture_subscribe

        await setup(app, sf, event_bus=event_bus)

        # Now invoke the captured handler with a mock event
        pid = str(uuid4())
        event = MagicMock()
        event.data = {"portfolio_id": pid}

        # The handler calls take_snapshot on the service — mock it
        app.state.risk_snapshot_service.take_snapshot = AsyncMock()

        await captured_handler(event)

        app.state.risk_snapshot_service.take_snapshot.assert_called_once()

    async def test_handler_skips_event_without_portfolio_id(self) -> None:
        app, sf = _make_app_and_sf()

        fund = MagicMock()
        fund.slug = "alpha"
        fund.id = str(uuid4())
        app.state.fund_repo.get_all_active.return_value = [fund]

        event_bus = MagicMock()
        captured_handler = None

        def capture_subscribe(topic, handler):
            nonlocal captured_handler
            captured_handler = handler

        event_bus.subscribe = capture_subscribe

        await setup(app, sf, event_bus=event_bus)

        event = MagicMock()
        event.data = {}  # no portfolio_id

        app.state.risk_snapshot_service.take_snapshot = AsyncMock()

        await captured_handler(event)

        # Should not call take_snapshot
        app.state.risk_snapshot_service.take_snapshot.assert_not_called()

    async def test_handler_catches_exception(self) -> None:
        app, sf = _make_app_and_sf()

        fund = MagicMock()
        fund.slug = "alpha"
        fund.id = str(uuid4())
        app.state.fund_repo.get_all_active.return_value = [fund]

        event_bus = MagicMock()
        captured_handler = None

        def capture_subscribe(topic, handler):
            nonlocal captured_handler
            captured_handler = handler

        event_bus.subscribe = capture_subscribe

        await setup(app, sf, event_bus=event_bus)

        event = MagicMock()
        event.data = {"portfolio_id": str(uuid4())}

        app.state.risk_snapshot_service.take_snapshot = AsyncMock(
            side_effect=Exception("snapshot failed")
        )

        # Should not raise
        await captured_handler(event)
