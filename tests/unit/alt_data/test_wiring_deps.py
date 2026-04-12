"""Unit tests for alt_data wiring and dependencies."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.alt_data.dependencies import get_alt_data_service
from app.modules.alt_data.services import AltDataService


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


class TestGetAltDataService:
    def test_returns_service_from_app_state(self) -> None:
        service = MagicMock(spec=AltDataService)
        request = MagicMock()
        request.app.state.alt_data_service = service

        result = get_alt_data_service(request)

        assert result is service

    def test_raises_503_when_not_initialized(self) -> None:
        from fastapi import HTTPException

        request = MagicMock()
        request.app.state = MagicMock(spec=[])  # no alt_data_service attr

        with pytest.raises(HTTPException) as exc_info:
            get_alt_data_service(request)

        assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


class TestSetup:
    @pytest.mark.asyncio
    async def test_wires_service_to_app_state(self) -> None:
        from app.modules.alt_data.wiring import setup

        app = MagicMock()
        sf = MagicMock()

        await setup(app, sf)

        assert hasattr(app.state, "alt_data_service")
        svc = app.state.alt_data_service
        assert isinstance(svc, AltDataService)

    @pytest.mark.asyncio
    async def test_wires_with_event_bus(self) -> None:
        from app.modules.alt_data.wiring import setup

        app = MagicMock()
        sf = MagicMock()
        event_bus = AsyncMock()

        await setup(app, sf, event_bus=event_bus)

        svc = app.state.alt_data_service
        assert isinstance(svc, AltDataService)

    @pytest.mark.asyncio
    async def test_wires_with_alt_data_provider(self) -> None:
        from app.modules.alt_data.wiring import setup

        app = MagicMock()
        sf = MagicMock()
        provider = MagicMock()

        await setup(app, sf, alt_data_provider=provider)

        svc = app.state.alt_data_service
        assert isinstance(svc, AltDataService)

    @pytest.mark.asyncio
    async def test_no_provider_means_empty_providers(self) -> None:
        from app.modules.alt_data.wiring import setup

        app = MagicMock()
        sf = MagicMock()

        await setup(app, sf)

        svc = app.state.alt_data_service
        assert svc._providers == []
