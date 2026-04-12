"""Unit tests for market data FastAPI dependency injection."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.modules.market_data.dependencies import get_market_data_service


class TestGetMarketDataService:
    def test_returns_service_when_available(self) -> None:
        request = MagicMock()
        request.app.state.market_data_service = MagicMock()

        result = get_market_data_service(request)

        assert result is not None

    def test_raises_503_when_service_not_initialized(self) -> None:
        request = MagicMock()
        request.app.state = MagicMock(spec=[])  # no market_data_service attribute

        with pytest.raises(HTTPException) as exc_info:
            get_market_data_service(request)

        assert exc_info.value.status_code == 503
        assert "not initialized" in exc_info.value.detail
