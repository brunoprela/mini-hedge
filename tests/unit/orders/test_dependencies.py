"""Unit tests for orders module FastAPI dependencies."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.modules.orders.dependencies import get_order_service


class TestGetOrderService:
    def test_returns_service_when_available(self) -> None:
        request = MagicMock()
        request.app.state.order_service = MagicMock()

        result = get_order_service(request)
        assert result is request.app.state.order_service

    def test_raises_503_when_not_initialized(self) -> None:
        request = MagicMock()
        request.app.state = MagicMock(spec=[])  # no order_service attr

        with pytest.raises(HTTPException) as exc_info:
            get_order_service(request)
        assert exc_info.value.status_code == 503
