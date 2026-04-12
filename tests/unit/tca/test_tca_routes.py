"""Unit tests for TCA route handler functions — verifies request handling,
service delegation, and error responses without a running server."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, PropertyMock
from uuid import UUID

import pytest
from fastapi import HTTPException

from app.modules.tca.routes.tca import (
    _get_tca_service,
    compute_order_tca,
    fund_tca_summary,
    get_order_tca,
    portfolio_tca,
)

_ORDER_ID = UUID("00000000-0000-0000-0000-000000000001")
_PORTFOLIO_ID = UUID("00000000-0000-0000-0000-000000000002")


def _make_request(*, tca_service=None) -> MagicMock:
    """Create a mock FastAPI Request with optional tca_service on app.state."""
    request = MagicMock()
    state = MagicMock()
    if tca_service is not None:
        state.tca_service = tca_service
    else:
        # Simulate attribute not set
        del state.tca_service
    request.app.state = state
    return request


def _make_tca_report(**overrides) -> MagicMock:
    r = MagicMock()
    r.order_id = _ORDER_ID
    r.instrument_id = "AAPL"
    r.side = "buy"
    r.quantity = Decimal("1000")
    r.filled_quantity = Decimal("1000")
    r.avg_fill_price = Decimal("150.50")
    r.arrival_mid_price = Decimal("150.00")
    r.arrival_spread = Decimal("0.10")
    r.vwap_benchmark = Decimal("150.25")
    r.total_cost_bps = Decimal("15.5000")
    r.commission_cost_bps = Decimal("5.0000")
    r.spread_cost_bps = Decimal("3.3333")
    r.market_impact_cost_bps = Decimal("5.0000")
    r.timing_cost_bps = Decimal("2.1667")
    r.opportunity_cost_bps = Decimal("0")
    r.implementation_shortfall_bps = Decimal("15.5000")
    r.participation_rate = None
    r.execution_duration_seconds = 1800
    r.total_cost_usd = Decimal("2325.00")
    r.computed_at = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    for k, v in overrides.items():
        setattr(r, k, v)
    return r


# ---------------------------------------------------------------------------
# _get_tca_service helper
# ---------------------------------------------------------------------------


class TestGetTcaService:
    def test_returns_service_when_available(self) -> None:
        svc = MagicMock()
        request = _make_request(tca_service=svc)
        assert _get_tca_service(request) is svc

    def test_raises_503_when_not_initialized(self) -> None:
        request = _make_request(tca_service=None)
        with pytest.raises(HTTPException) as exc_info:
            _get_tca_service(request)
        assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# GET /orders/{order_id}/tca
# ---------------------------------------------------------------------------


class TestGetOrderTca:
    @pytest.mark.asyncio
    async def test_returns_report(self) -> None:
        report = _make_tca_report()
        svc = AsyncMock()
        svc.get_for_order = AsyncMock(return_value=report)
        request = _make_request(tca_service=svc)
        session = AsyncMock()
        ctx = MagicMock()

        result = await get_order_tca(_ORDER_ID, request, ctx, session)
        assert result is report

    @pytest.mark.asyncio
    async def test_raises_404_when_no_tca(self) -> None:
        svc = AsyncMock()
        svc.get_for_order = AsyncMock(return_value=None)
        request = _make_request(tca_service=svc)
        session = AsyncMock()
        ctx = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_order_tca(_ORDER_ID, request, ctx, session)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# POST /orders/{order_id}/tca/compute
# ---------------------------------------------------------------------------


class TestComputeOrderTca:
    @pytest.mark.asyncio
    async def test_returns_computed_report(self) -> None:
        report = _make_tca_report()
        svc = AsyncMock()
        svc.compute_for_order = AsyncMock(return_value=report)
        request = _make_request(tca_service=svc)
        session = AsyncMock()
        ctx = MagicMock()

        result = await compute_order_tca(_ORDER_ID, request, ctx, session)
        assert result is report

    @pytest.mark.asyncio
    async def test_raises_400_when_not_eligible(self) -> None:
        svc = AsyncMock()
        svc.compute_for_order = AsyncMock(return_value=None)
        request = _make_request(tca_service=svc)
        session = AsyncMock()
        ctx = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await compute_order_tca(_ORDER_ID, request, ctx, session)
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# GET /orders/tca/portfolio/{portfolio_id}
# ---------------------------------------------------------------------------


class TestPortfolioTca:
    @pytest.mark.asyncio
    async def test_returns_portfolio_report(self) -> None:
        portfolio_report = MagicMock()
        svc = AsyncMock()
        svc.get_portfolio_report = AsyncMock(return_value=portfolio_report)
        request = _make_request(tca_service=svc)
        session = AsyncMock()
        ctx = MagicMock()

        result = await portfolio_tca(_PORTFOLIO_ID, request, ctx, session)
        assert result is portfolio_report
        svc.get_portfolio_report.assert_awaited_once_with(
            _PORTFOLIO_ID, session=session
        )


# ---------------------------------------------------------------------------
# GET /orders/tca/summary
# ---------------------------------------------------------------------------


class TestFundTcaSummary:
    @pytest.mark.asyncio
    async def test_returns_fund_summary(self) -> None:
        summary = MagicMock()
        svc = AsyncMock()
        svc.get_fund_summary = AsyncMock(return_value=summary)
        request = _make_request(tca_service=svc)
        ctx = MagicMock()
        ctx.fund_slug = "alpha"

        result = await fund_tca_summary(request, ctx, days=30)
        assert result is summary
        svc.get_fund_summary.assert_awaited_once()
        call_args = svc.get_fund_summary.call_args
        assert call_args[0][0] == "alpha"
