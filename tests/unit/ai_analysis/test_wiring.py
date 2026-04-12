"""Unit tests for ai_analysis wiring and module imports."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestLLMAdapterReExport:
    def test_llm_adapter_protocol_importable(self):
        from app.modules.ai_analysis.core.llm_adapter import LLMAdapter, LLMResponse

        assert LLMAdapter is not None
        assert LLMResponse is not None


class TestWiringSetup:
    @pytest.mark.asyncio
    async def test_setup_creates_service_on_app_state(self):
        from app.modules.ai_analysis.wiring import setup

        app = MagicMock()
        app.state = MagicMock()
        sf = MagicMock()
        event_bus = AsyncMock()
        llm_adapter = AsyncMock()

        await setup(app, sf, event_bus=event_bus, llm_adapter=llm_adapter)

        # Verify service was assigned to app state
        assert hasattr(app.state, "ai_analysis_service")
        svc = app.state.ai_analysis_service
        from app.modules.ai_analysis.services import AIAnalysisService

        assert isinstance(svc, AIAnalysisService)
