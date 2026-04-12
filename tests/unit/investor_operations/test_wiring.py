"""Unit tests for investor_operations.wiring.setup — verifies repos, services, and state wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSetup:
    @pytest.mark.asyncio
    @patch.dict("os.environ", {"APP_ENV": "test"}, clear=False)
    @patch("app.adapters.factory.build_kyc_screening_adapter")
    async def test_wires_services_onto_app_state(self, mock_build_kyc: MagicMock) -> None:
        from app.modules.investor_operations.wiring import setup

        mock_build_kyc.return_value = MagicMock()

        app = MagicMock()
        app.state.capital_transaction_service = AsyncMock()
        sf = MagicMock()
        event_bus = AsyncMock()

        await setup(app, sf, event_bus=event_bus, settings=None)

        # Verify all three services are set on app.state
        assert hasattr(app.state, "subscription_service")
        assert hasattr(app.state, "redemption_service")
        assert hasattr(app.state, "kyc_service")

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"APP_ENV": "local"}, clear=False)
    @patch("app.adapters.factory.build_kyc_screening_adapter")
    @patch("app.modules.investor_operations.seed.seed_dev_data", new_callable=AsyncMock)
    async def test_seeds_in_local_env(
        self, mock_seed: AsyncMock, mock_build_kyc: MagicMock
    ) -> None:
        from app.modules.investor_operations.wiring import setup

        mock_build_kyc.return_value = MagicMock()

        app = MagicMock()
        app.state.capital_transaction_service = AsyncMock()
        sf = MagicMock()

        await setup(app, sf, event_bus=AsyncMock(), settings=None)

        mock_seed.assert_called_once_with(app, sf)

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"APP_ENV": "production"}, clear=False)
    @patch("app.adapters.factory.build_kyc_screening_adapter")
    async def test_no_seed_in_production(self, mock_build_kyc: MagicMock) -> None:
        from app.modules.investor_operations.wiring import setup

        mock_build_kyc.return_value = MagicMock()

        app = MagicMock()
        app.state.capital_transaction_service = AsyncMock()
        sf = MagicMock()

        with patch(
            "app.modules.investor_operations.seed.seed_dev_data", new_callable=AsyncMock
        ) as mock_seed:
            await setup(app, sf, event_bus=AsyncMock(), settings=None)
            mock_seed.assert_not_called()
