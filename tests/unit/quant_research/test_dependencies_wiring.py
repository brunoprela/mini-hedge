"""Unit tests for quant_research dependencies and wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.quant_research.dependencies import get_quant_research_service


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


class TestGetQuantResearchService:
    def test_returns_service_from_app_state(self):
        service = MagicMock()
        request = MagicMock()
        request.app.state.quant_research_service = service

        result = get_quant_research_service(request)
        assert result is service

    def test_raises_503_when_not_initialized(self):
        request = MagicMock()
        request.app.state = MagicMock(spec=[])  # no quant_research_service attr

        with pytest.raises(HTTPException) as exc_info:
            get_quant_research_service(request)
        assert exc_info.value.status_code == 503
        assert "QuantResearchService" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


class TestWiring:
    @pytest.mark.asyncio
    async def test_setup_wires_service_onto_app(self):
        from app.modules.quant_research.wiring import setup

        app = MagicMock()
        sf = MagicMock()
        event_bus = MagicMock()

        await setup(app, sf, event_bus=event_bus)

        # The service should be attached to app.state
        assert hasattr(app.state, "quant_research_service")
        svc = app.state.quant_research_service
        # Verify it's a QuantResearchService instance
        from app.modules.quant_research.services import QuantResearchService

        assert isinstance(svc, QuantResearchService)

    @pytest.mark.asyncio
    async def test_setup_without_event_bus(self):
        from app.modules.quant_research.wiring import setup

        app = MagicMock()
        sf = MagicMock()

        await setup(app, sf)

        assert hasattr(app.state, "quant_research_service")


# ---------------------------------------------------------------------------
# Repository __init__ re-exports
# ---------------------------------------------------------------------------


class TestRepositoryReExports:
    def test_imports_from_package(self):
        from app.modules.quant_research.repositories import (
            FactorDefinitionRepository,
            FactorExposureRepository,
            FactorReturnRepository,
            RegimeRepository,
        )

        assert FactorDefinitionRepository is not None
        assert FactorExposureRepository is not None
        assert FactorReturnRepository is not None
        assert RegimeRepository is not None
