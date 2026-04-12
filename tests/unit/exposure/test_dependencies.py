"""Unit tests for exposure FastAPI dependency injection."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.modules.exposure.dependencies import get_exposure_service


class TestGetExposureService:
    def test_returns_service_when_available(self) -> None:
        mock_service = MagicMock()
        request = MagicMock()
        request.app.state.exposure_service = mock_service

        result = get_exposure_service(request)

        assert result is mock_service

    def test_raises_503_when_service_not_initialized(self) -> None:
        request = MagicMock()
        request.app.state.exposure_service = None

        with pytest.raises(HTTPException) as exc_info:
            get_exposure_service(request)

        assert exc_info.value.status_code == 503

    def test_raises_503_when_attribute_missing(self) -> None:
        request = MagicMock()
        # Simulate missing attribute by having getattr return None
        del request.app.state.exposure_service
        request.app.state.configure_mock(**{})
        type(request.app.state).exposure_service = property(
            lambda self: (_ for _ in ()).throw(AttributeError)
        )

        # MagicMock won't raise AttributeError on getattr, so we need a
        # real object without the attribute
        class FakeState:
            pass

        class FakeApp:
            state = FakeState()

        class FakeRequest:
            app = FakeApp()

        with pytest.raises(HTTPException) as exc_info:
            get_exposure_service(FakeRequest())  # type: ignore[arg-type]

        assert exc_info.value.status_code == 503
