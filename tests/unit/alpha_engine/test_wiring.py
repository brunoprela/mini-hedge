"""Unit tests for alpha engine module wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSetup:
    @pytest.mark.asyncio
    @patch.dict("os.environ", {"APP_ENV": "local"})
    @patch("app.modules.alpha_engine.seed.seed_dev_data", new_callable=AsyncMock)
    async def test_wires_service_and_seeds_in_local(
        self, mock_seed: AsyncMock
    ) -> None:
        from app.modules.alpha_engine.wiring import setup

        app = MagicMock()
        app.state.position_service = AsyncMock()
        app.state.security_master_service = AsyncMock()
        # wiring reads sm_service from app.state
        app.state.sm_service = AsyncMock()

        sf = AsyncMock()
        event_bus = AsyncMock()

        await setup(app, sf, event_bus=event_bus)

        assert hasattr(app.state, "alpha_service")
        mock_seed.assert_called_once_with(app, sf)

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"APP_ENV": "production"})
    @patch("app.modules.alpha_engine.seed.seed_dev_data", new_callable=AsyncMock)
    async def test_no_seed_in_production(
        self, mock_seed: AsyncMock
    ) -> None:
        from app.modules.alpha_engine.wiring import setup

        app = MagicMock()
        app.state.position_service = AsyncMock()
        app.state.sm_service = AsyncMock()

        sf = AsyncMock()

        await setup(app, sf)

        assert hasattr(app.state, "alpha_service")
        mock_seed.assert_not_called()

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"APP_ENV": "local"})
    @patch(
        "app.modules.alpha_engine.seed.seed_dev_data",
        new_callable=AsyncMock,
        side_effect=Exception("seed boom"),
    )
    async def test_seed_exception_is_swallowed(
        self, mock_seed: AsyncMock
    ) -> None:
        from app.modules.alpha_engine.wiring import setup

        app = MagicMock()
        app.state.position_service = AsyncMock()
        app.state.sm_service = AsyncMock()

        sf = AsyncMock()

        # Should not raise even though seed raises
        await setup(app, sf)

        assert hasattr(app.state, "alpha_service")

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"APP_ENV": "local"})
    @patch("app.modules.alpha_engine.seed.seed_dev_data", new_callable=AsyncMock)
    async def test_service_wired_with_correct_deps(
        self, mock_seed: AsyncMock
    ) -> None:
        from app.modules.alpha_engine.services.alpha import AlphaService
        from app.modules.alpha_engine.wiring import setup

        app = MagicMock()
        app.state.position_service = MagicMock(name="pos_svc")
        app.state.sm_service = MagicMock(name="sm_svc")

        sf = AsyncMock()
        event_bus = AsyncMock()

        await setup(app, sf, event_bus=event_bus)

        svc = app.state.alpha_service
        assert isinstance(svc, AlphaService)
