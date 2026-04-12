"""Unit tests for FX hedging dependencies module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.modules.fx_hedging.dependencies import get_fx_hedging_service


class TestGetFxHedgingService:
    def test_returns_service_when_available(self) -> None:
        request = MagicMock()
        request.app.state.fx_hedging_service = MagicMock()

        result = get_fx_hedging_service(request)

        assert result is request.app.state.fx_hedging_service

    def test_raises_503_when_not_initialized(self) -> None:
        from fastapi import HTTPException

        request = MagicMock()
        # Simulate missing attribute
        request.app.state = MagicMock(spec=[])

        with pytest.raises(HTTPException) as exc_info:
            get_fx_hedging_service(request)

        assert exc_info.value.status_code == 503
        assert "not initialized" in exc_info.value.detail
