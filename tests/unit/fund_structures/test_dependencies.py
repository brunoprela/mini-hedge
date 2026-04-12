"""Unit tests for fund_structures.dependencies."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.modules.fund_structures.dependencies import get_fund_structures_service


class TestGetFundStructuresService:
    def test_returns_service_when_available(self) -> None:
        request = MagicMock()
        request.app.state.fund_structures_service = MagicMock()

        result = get_fund_structures_service(request)

        assert result is request.app.state.fund_structures_service

    def test_raises_503_when_service_not_initialised(self) -> None:
        request = MagicMock()
        # Simulate missing attribute
        del request.app.state.fund_structures_service

        with pytest.raises(HTTPException) as exc_info:
            get_fund_structures_service(request)

        assert exc_info.value.status_code == 503
        assert "FundStructuresService" in exc_info.value.detail
