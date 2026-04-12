"""Unit tests for FastAPI dependency getters."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.modules.platform.dependencies import (
    get_admin_service,
    get_archival_service,
    get_audit_repo,
    get_audit_verifier,
    get_auth_service,
    get_portfolio_repo,
)


def _make_request(state_attrs: dict | None = None) -> MagicMock:
    """Create a mock Request with app.state attributes."""
    request = MagicMock()
    state = MagicMock()
    if state_attrs:
        for k, v in state_attrs.items():
            setattr(state, k, v)
    else:
        # No attributes set — getattr will return default None
        state = MagicMock(spec=[])
    request.app.state = state
    return request


class TestGetAuthService:
    def test_returns_service(self) -> None:
        svc = MagicMock()
        request = _make_request({"auth_service": svc})

        result = get_auth_service(request)

        assert result is svc

    def test_raises_503_when_missing(self) -> None:
        request = _make_request()

        with pytest.raises(HTTPException) as exc_info:
            get_auth_service(request)

        assert exc_info.value.status_code == 503


class TestGetPortfolioRepo:
    def test_returns_repo(self) -> None:
        repo = MagicMock()
        request = _make_request({"portfolio_repo": repo})

        result = get_portfolio_repo(request)

        assert result is repo

    def test_raises_503_when_missing(self) -> None:
        request = _make_request()

        with pytest.raises(HTTPException) as exc_info:
            get_portfolio_repo(request)

        assert exc_info.value.status_code == 503


class TestGetAdminService:
    def test_returns_service(self) -> None:
        svc = MagicMock()
        request = _make_request({"admin_service": svc})

        result = get_admin_service(request)

        assert result is svc

    def test_raises_503_when_missing(self) -> None:
        request = _make_request()

        with pytest.raises(HTTPException) as exc_info:
            get_admin_service(request)

        assert exc_info.value.status_code == 503


class TestGetAuditRepo:
    def test_returns_repo(self) -> None:
        repo = MagicMock()
        request = _make_request({"audit_repo": repo})

        result = get_audit_repo(request)

        assert result is repo

    def test_raises_503_when_missing(self) -> None:
        request = _make_request()

        with pytest.raises(HTTPException) as exc_info:
            get_audit_repo(request)

        assert exc_info.value.status_code == 503


class TestGetAuditVerifier:
    def test_returns_verifier(self) -> None:
        verifier = MagicMock()
        request = _make_request({"audit_verifier": verifier})

        result = get_audit_verifier(request)

        assert result is verifier

    def test_raises_503_when_missing(self) -> None:
        request = _make_request()

        with pytest.raises(HTTPException) as exc_info:
            get_audit_verifier(request)

        assert exc_info.value.status_code == 503


class TestGetArchivalService:
    def test_returns_service(self) -> None:
        svc = MagicMock()
        request = _make_request({"archival_service": svc})

        result = get_archival_service(request)

        assert result is svc

    def test_raises_503_when_missing(self) -> None:
        request = _make_request()

        with pytest.raises(HTTPException) as exc_info:
            get_archival_service(request)

        assert exc_info.value.status_code == 503
