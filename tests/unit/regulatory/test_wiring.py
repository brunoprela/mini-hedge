"""Unit tests for regulatory module wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSetup:
    @pytest.mark.asyncio
    @patch.dict("os.environ", {"APP_ENV": "local"})
    @patch("app.modules.regulatory.seed.seed_dev_data", new_callable=AsyncMock)
    async def test_wires_service_and_seeds_in_local(
        self, mock_seed: AsyncMock
    ) -> None:
        from app.modules.regulatory.wiring import setup

        app = MagicMock()
        app.state.position_service = AsyncMock()
        app.state.capital_service = AsyncMock()
        app.state.counterparty_risk_service = AsyncMock()
        app.state.exposure_service = AsyncMock()
        app.state.sm_service = AsyncMock()

        sf = AsyncMock()
        event_bus = AsyncMock()

        await setup(app, sf, event_bus=event_bus)

        assert hasattr(app.state, "regulatory_service")
        mock_seed.assert_called_once_with(app, sf)

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"APP_ENV": "production"})
    @patch("app.modules.regulatory.seed.seed_dev_data", new_callable=AsyncMock)
    async def test_wires_service_no_seed_in_prod(
        self, mock_seed: AsyncMock
    ) -> None:
        from app.modules.regulatory.wiring import setup

        app = MagicMock()
        app.state.position_service = AsyncMock()
        sf = AsyncMock()

        await setup(app, sf)

        assert hasattr(app.state, "regulatory_service")
        mock_seed.assert_not_called()

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"APP_ENV": "local"})
    @patch("app.modules.regulatory.seed.seed_dev_data", new_callable=AsyncMock)
    async def test_service_gets_deps_from_app_state(
        self, mock_seed: AsyncMock
    ) -> None:
        from app.modules.regulatory.services.regulatory import RegulatoryService
        from app.modules.regulatory.wiring import setup

        app = MagicMock()
        app.state.position_service = MagicMock(name="pos_svc")
        app.state.capital_service = MagicMock(name="cap_svc")
        app.state.counterparty_risk_service = MagicMock(name="risk_svc")
        app.state.exposure_service = MagicMock(name="exp_svc")
        app.state.sm_service = MagicMock(name="sm_svc")

        sf = AsyncMock()
        event_bus = AsyncMock()

        await setup(app, sf, event_bus=event_bus)

        svc = app.state.regulatory_service
        assert isinstance(svc, RegulatoryService)
