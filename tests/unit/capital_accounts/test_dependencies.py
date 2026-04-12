"""Unit tests for capital accounts FastAPI dependency functions."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.modules.capital_accounts.dependencies import (
    get_capital_account_service,
    get_capital_transaction_service,
    get_investor_repo,
)


def _make_request(*, attrs: dict | None = None) -> MagicMock:
    request = MagicMock()
    state = MagicMock()
    if attrs:
        for k, v in attrs.items():
            setattr(state, k, v)
    else:
        # Make getattr return None for missing attributes
        state.configure_mock(**{"__getattr__": lambda self, name: None})

    request.app.state = state
    return request


class TestGetCapitalAccountService:
    def test_returns_service_when_present(self) -> None:
        svc = MagicMock()
        request = _make_request(attrs={"capital_account_service": svc})
        assert get_capital_account_service(request) is svc

    def test_raises_503_when_missing(self) -> None:
        request = MagicMock()
        request.app.state = MagicMock(spec=[])  # no attributes
        with pytest.raises(HTTPException) as exc_info:
            get_capital_account_service(request)
        assert exc_info.value.status_code == 503
        assert "CapitalAccountService" in exc_info.value.detail


class TestGetInvestorRepo:
    def test_returns_repo_when_present(self) -> None:
        repo = MagicMock()
        request = _make_request(attrs={"investor_repo": repo})
        assert get_investor_repo(request) is repo

    def test_raises_503_when_missing(self) -> None:
        request = MagicMock()
        request.app.state = MagicMock(spec=[])
        with pytest.raises(HTTPException) as exc_info:
            get_investor_repo(request)
        assert exc_info.value.status_code == 503
        assert "InvestorRepository" in exc_info.value.detail


class TestGetCapitalTransactionService:
    def test_returns_service_when_present(self) -> None:
        svc = MagicMock()
        request = _make_request(attrs={"capital_transaction_service": svc})
        assert get_capital_transaction_service(request) is svc

    def test_raises_503_when_missing(self) -> None:
        request = MagicMock()
        request.app.state = MagicMock(spec=[])
        with pytest.raises(HTTPException) as exc_info:
            get_capital_transaction_service(request)
        assert exc_info.value.status_code == 503
        assert "CapitalTransactionService" in exc_info.value.detail
