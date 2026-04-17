"""Unit tests for investor_operations.wiring.setup — verifies repos, services, and state wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSetup:
    @pytest.mark.asyncio
    @patch.dict("os.environ", {"APP_ENV": "test"}, clear=False)
    async def test_wires_services_onto_app_state(self) -> None:
        from app.modules.investor_operations.wiring import setup

        app = MagicMock()
        app.state.capital_transaction_service = AsyncMock()
        sf = MagicMock()
        event_bus = AsyncMock()
        kyc_adapter = MagicMock()

        await setup(app, sf, event_bus=event_bus, settings=None, kyc_adapter=kyc_adapter)

        # Verify all three services are set on app.state
        assert hasattr(app.state, "subscription_service")
        assert hasattr(app.state, "redemption_service")
        assert hasattr(app.state, "kyc_service")

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"APP_ENV": "local"}, clear=False)
    @patch("app.modules.investor_operations.seed.seed_dev_data", new_callable=AsyncMock)
    async def test_seeds_in_local_env(self, mock_seed: AsyncMock) -> None:
        from app.modules.investor_operations.wiring import setup

        app = MagicMock()
        app.state.capital_transaction_service = AsyncMock()
        sf = MagicMock()
        kyc_adapter = MagicMock()

        await setup(app, sf, event_bus=AsyncMock(), settings=None, kyc_adapter=kyc_adapter)

        mock_seed.assert_called_once_with(app, sf)

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"APP_ENV": "production"}, clear=False)
    async def test_no_seed_in_production(self) -> None:
        from app.modules.investor_operations.wiring import setup

        app = MagicMock()
        app.state.capital_transaction_service = AsyncMock()
        sf = MagicMock()
        kyc_adapter = MagicMock()

        with patch(
            "app.modules.investor_operations.seed.seed_dev_data", new_callable=AsyncMock
        ) as mock_seed:
            await setup(app, sf, event_bus=AsyncMock(), settings=None, kyc_adapter=kyc_adapter)
            mock_seed.assert_not_called()

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"APP_ENV": "test"}, clear=False)
    async def test_requires_kyc_adapter(self) -> None:
        from app.modules.investor_operations.wiring import setup

        app = MagicMock()
        app.state.capital_transaction_service = AsyncMock()
        sf = MagicMock()

        with pytest.raises(RuntimeError, match="KYCScreeningAdapter"):
            await setup(app, sf, event_bus=AsyncMock(), settings=None)
