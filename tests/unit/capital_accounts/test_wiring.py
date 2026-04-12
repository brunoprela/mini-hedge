"""Unit tests for capital accounts module wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.capital_accounts.wiring import setup


def _make_app() -> MagicMock:
    app = MagicMock()
    app.state = MagicMock(spec=[])  # Start with empty state
    app.state.cash_service = None  # Explicitly set
    return app


def _make_session_factory() -> MagicMock:
    sf = MagicMock()
    return sf


class TestSetup:
    @pytest.mark.asyncio
    @patch.dict("os.environ", {"APP_ENV": "production"}, clear=False)
    async def test_wires_services_and_repos(self) -> None:
        """setup() creates repos and services and attaches them to app.state."""
        app = _make_app()
        sf = _make_session_factory()

        await setup(app, sf)

        assert hasattr(app.state, "capital_account_service")
        assert hasattr(app.state, "capital_transaction_service")
        assert hasattr(app.state, "investor_repo")

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"APP_ENV": "production"}, clear=False)
    async def test_wires_with_event_bus(self) -> None:
        app = _make_app()
        sf = _make_session_factory()
        event_bus = AsyncMock()

        await setup(app, sf, event_bus=event_bus)

        assert hasattr(app.state, "capital_transaction_service")

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"APP_ENV": "local"}, clear=False)
    @patch(
        "app.modules.capital_accounts.seed.seed_dev_data",
        new_callable=AsyncMock,
    )
    async def test_seeds_in_local_env(self, mock_seed: AsyncMock) -> None:
        app = _make_app()
        sf = _make_session_factory()

        await setup(app, sf)

        mock_seed.assert_called_once_with(app, sf)

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"APP_ENV": "production"}, clear=False)
    @patch(
        "app.modules.capital_accounts.seed.seed_dev_data",
        new_callable=AsyncMock,
    )
    async def test_does_not_seed_in_production(self, mock_seed: AsyncMock) -> None:
        app = _make_app()
        sf = _make_session_factory()

        await setup(app, sf)

        mock_seed.assert_not_called()

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"APP_ENV": "production"}, clear=False)
    async def test_picks_up_cash_service_from_app_state(self) -> None:
        app = _make_app()
        app.state.cash_service = MagicMock()
        sf = _make_session_factory()

        await setup(app, sf)

        assert hasattr(app.state, "capital_transaction_service")
