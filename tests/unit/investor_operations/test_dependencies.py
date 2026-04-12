"""Unit tests for investor_operations.dependencies — FastAPI dependency wrappers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.modules.investor_operations.dependencies import (
    get_kyc_service,
    get_redemption_service,
    get_subscription_service,
)


def _make_request(*, subscription_service=None, redemption_service=None, kyc_service=None):
    request = MagicMock()
    state = MagicMock()
    # Use spec=[] so getattr returns the value we set, not auto-mocks
    if subscription_service is not None:
        state.subscription_service = subscription_service
    else:
        # Simulate missing attribute
        del state.subscription_service
    if redemption_service is not None:
        state.redemption_service = redemption_service
    else:
        del state.redemption_service
    if kyc_service is not None:
        state.kyc_service = kyc_service
    else:
        del state.kyc_service
    request.app.state = state
    return request


class TestGetSubscriptionService:
    def test_returns_service_when_present(self) -> None:
        svc = MagicMock()
        request = _make_request(subscription_service=svc)
        assert get_subscription_service(request) is svc

    def test_raises_503_when_missing(self) -> None:
        request = _make_request()
        with pytest.raises(HTTPException) as exc_info:
            get_subscription_service(request)
        assert exc_info.value.status_code == 503


class TestGetRedemptionService:
    def test_returns_service_when_present(self) -> None:
        svc = MagicMock()
        request = _make_request(redemption_service=svc)
        assert get_redemption_service(request) is svc

    def test_raises_503_when_missing(self) -> None:
        request = _make_request()
        with pytest.raises(HTTPException) as exc_info:
            get_redemption_service(request)
        assert exc_info.value.status_code == 503


class TestGetKycService:
    def test_returns_service_when_present(self) -> None:
        svc = MagicMock()
        request = _make_request(kyc_service=svc)
        assert get_kyc_service(request) is svc

    def test_raises_503_when_missing(self) -> None:
        request = _make_request()
        with pytest.raises(HTTPException) as exc_info:
            get_kyc_service(request)
        assert exc_info.value.status_code == 503
