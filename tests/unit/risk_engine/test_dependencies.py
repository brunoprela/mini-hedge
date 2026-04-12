"""Unit tests for risk engine FastAPI dependency injectors."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.modules.risk_engine.dependencies import (
    get_counterparty_risk_service,
    get_liquidity_margin_service,
    get_risk_snapshot_service,
)


def _make_request(*, attrs: dict | None = None) -> MagicMock:
    request = MagicMock()
    state = MagicMock(spec=list(attrs.keys()) if attrs else [])
    for k, v in (attrs or {}).items():
        setattr(state, k, v)
    request.app.state = state
    return request


class TestGetRiskSnapshotService:
    def test_returns_service_when_available(self) -> None:
        svc = MagicMock()
        request = _make_request(attrs={"risk_snapshot_service": svc})
        assert get_risk_snapshot_service(request) is svc

    def test_raises_503_when_not_initialized(self) -> None:
        request = _make_request()
        with pytest.raises(HTTPException) as exc_info:
            get_risk_snapshot_service(request)
        assert exc_info.value.status_code == 503


class TestGetCounterpartyRiskService:
    def test_returns_service_when_available(self) -> None:
        svc = MagicMock()
        request = _make_request(attrs={"counterparty_risk_service": svc})
        assert get_counterparty_risk_service(request) is svc

    def test_raises_503_when_not_initialized(self) -> None:
        request = _make_request()
        with pytest.raises(HTTPException) as exc_info:
            get_counterparty_risk_service(request)
        assert exc_info.value.status_code == 503


class TestGetLiquidityMarginService:
    def test_returns_service_when_available(self) -> None:
        svc = MagicMock()
        request = _make_request(attrs={"liquidity_margin_service": svc})
        assert get_liquidity_margin_service(request) is svc

    def test_raises_503_when_not_initialized(self) -> None:
        request = _make_request()
        with pytest.raises(HTTPException) as exc_info:
            get_liquidity_margin_service(request)
        assert exc_info.value.status_code == 503
