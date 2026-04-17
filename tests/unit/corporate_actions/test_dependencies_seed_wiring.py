"""Unit tests for corporate actions dependencies, seed, and wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.corporate_actions.dependencies import get_corporate_actions_service


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


class TestGetCorporateActionsService:
    def test_returns_service_from_app_state(self):
        service = MagicMock()
        request = MagicMock()
        request.app.state.corporate_actions_service = service

        result = get_corporate_actions_service(request)
        assert result is service

    def test_raises_503_when_not_initialized(self):
        from fastapi import HTTPException

        request = MagicMock()
        request.app.state = MagicMock(spec=[])  # no corporate_actions_service attr

        with pytest.raises(HTTPException) as exc_info:
            get_corporate_actions_service(request)
        assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------


class TestSeedDevData:
    @pytest.mark.asyncio
    async def test_skips_when_no_service(self):
        """seed_dev_data returns early when corporate_actions_service is not on app.state."""
        from app.modules.corporate_actions.seed import seed_dev_data

        app = MagicMock()
        app.state = MagicMock(spec=[])  # no corporate_actions_service attr
        sf = MagicMock()

        await seed_dev_data(app, sf)
        # Should not raise — just logs and returns

    @pytest.mark.asyncio
    async def test_seeds_when_no_existing_actions(self):
        """seed_dev_data inserts seed records when none exist."""
        from app.modules.corporate_actions.seed import seed_dev_data

        ca_repo = AsyncMock()
        ca_repo.get_by_action_id = AsyncMock(return_value=None)
        ca_repo.insert = AsyncMock()

        service = MagicMock()
        service._repo = ca_repo

        fund = MagicMock()
        fund.slug = "alpha"
        fund_repo = AsyncMock()
        fund_repo.list_active = AsyncMock(return_value=[fund])

        app = MagicMock()
        app.state.corporate_actions_service = service
        app.state.fund_repo = fund_repo

        sf = MagicMock()
        sf.fund_scope = MagicMock(return_value=AsyncMock())

        await seed_dev_data(app, sf)

        # 4 seed actions defined in _SEED_ACTIONS
        assert ca_repo.insert.call_count == 4
        assert ca_repo.get_by_action_id.call_count == 4

    @pytest.mark.asyncio
    async def test_skips_existing_actions(self):
        """seed_dev_data skips actions that already exist."""
        from app.modules.corporate_actions.seed import seed_dev_data

        ca_repo = AsyncMock()
        ca_repo.get_by_action_id = AsyncMock(return_value=MagicMock())  # already exists
        ca_repo.insert = AsyncMock()

        service = MagicMock()
        service._repo = ca_repo

        fund = MagicMock()
        fund.slug = "alpha"
        fund_repo = AsyncMock()
        fund_repo.list_active = AsyncMock(return_value=[fund])

        app = MagicMock()
        app.state.corporate_actions_service = service
        app.state.fund_repo = fund_repo

        sf = MagicMock()
        sf.fund_scope = MagicMock(return_value=AsyncMock())

        await seed_dev_data(app, sf)

        ca_repo.insert.assert_not_called()


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


class TestWiringSetup:
    @pytest.mark.asyncio
    async def test_wires_service_to_app_state(self):
        """setup attaches corporate_actions_service to app.state."""
        from app.modules.corporate_actions.wiring import setup

        app = MagicMock()
        app.state.position_service = MagicMock()
        sf = MagicMock()
        event_bus = MagicMock()
        settings = MagicMock()

        with (
            patch(
                "app.adapters.factory.build_corporate_actions_adapter",
            ) as mock_adapter_factory,
            patch(
                "app.modules.corporate_actions.repositories.CorporateActionsRepository",
            ),
            patch(
                "app.modules.corporate_actions.services.CorporateActionsService",
            ) as mock_svc_cls,
            patch(
                "app.modules.corporate_actions.seed.seed_dev_data",
                new_callable=AsyncMock,
            ) as mock_seed,
            patch.dict("os.environ", {"APP_ENV": "local"}),
        ):
            mock_adapter_factory.return_value = MagicMock()
            mock_svc_cls.return_value = MagicMock()

            await setup(app, sf, event_bus=event_bus, settings=settings)

            assert app.state.corporate_actions_service == mock_svc_cls.return_value
            mock_seed.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_seed_in_production(self):
        """setup does not call seed_dev_data when APP_ENV != local."""
        from app.modules.corporate_actions.wiring import setup

        app = MagicMock()
        app.state.position_service = MagicMock()
        sf = MagicMock()
        event_bus = MagicMock()
        settings = MagicMock()

        with (
            patch(
                "app.adapters.factory.build_corporate_actions_adapter",
            ) as mock_adapter_factory,
            patch(
                "app.modules.corporate_actions.repositories.CorporateActionsRepository",
            ),
            patch(
                "app.modules.corporate_actions.services.CorporateActionsService",
            ) as mock_svc_cls,
            patch.dict("os.environ", {"APP_ENV": "production"}),
        ):
            mock_adapter_factory.return_value = MagicMock()
            mock_svc_cls.return_value = MagicMock()

            await setup(app, sf, event_bus=event_bus, settings=settings)

            # Service still wired
            assert app.state.corporate_actions_service == mock_svc_cls.return_value
