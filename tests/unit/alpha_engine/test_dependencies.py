"""Unit tests for alpha engine FastAPI dependency injection."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.modules.alpha_engine.dependencies import get_alpha_service


class TestGetAlphaService:
    def test_returns_service_when_available(self) -> None:
        mock_service = MagicMock()
        request = MagicMock()
        request.app.state.alpha_service = mock_service

        result = get_alpha_service(request)

        assert result is mock_service

    def test_raises_503_when_service_is_none(self) -> None:
        request = MagicMock()
        request.app.state.alpha_service = None

        with pytest.raises(HTTPException) as exc_info:
            get_alpha_service(request)

        assert exc_info.value.status_code == 503

    def test_raises_503_when_attribute_missing(self) -> None:
        class FakeState:
            pass

        class FakeApp:
            state = FakeState()

        class FakeRequest:
            app = FakeApp()

        with pytest.raises(HTTPException) as exc_info:
            get_alpha_service(FakeRequest())  # type: ignore[arg-type]

        assert exc_info.value.status_code == 503
