"""Unit tests for regulatory dependencies."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.modules.regulatory.dependencies import get_regulatory_service


class TestGetRegulatoryService:
    def test_returns_service_from_app_state(self) -> None:
        svc = MagicMock()
        request = MagicMock()
        request.app.state.regulatory_service = svc

        result = get_regulatory_service(request)

        assert result is svc
