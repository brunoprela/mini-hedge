"""FastAPI routes for Transaction Cost Analysis."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.modules.orders.tca.interface import (
    FundTCASummary,
    PortfolioTCAReport,
    TCAReport,
)
from app.shared.auth import Permission, require_permission
from app.shared.database import get_db, get_read_db

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.orders.tca.service import TCAService
    from app.shared.auth.request_context import RequestContext

router = APIRouter(tags=["tca"])


def _get_tca_service(request: Request) -> TCAService:
    svc = getattr(request.app.state, "tca_service", None)
    if svc is None:
        raise HTTPException(503, "TCAService not initialized")
    return cast("TCAService", svc)


@router.get("/orders/{order_id}/tca", response_model=TCAReport)
async def get_order_tca(
    order_id: UUID,
    request: Request,
    request_context: RequestContext = require_permission(Permission.ORDERS_READ),
    session: AsyncSession = Depends(get_read_db),
) -> TCAReport:
    """Get TCA results for a specific order."""
    svc = _get_tca_service(request)
    report = await svc.get_for_order(order_id, session=session)
    if report is None:
        raise HTTPException(404, f"No TCA results for order {order_id}")
    return report


@router.post("/orders/{order_id}/tca/compute", response_model=TCAReport)
async def compute_order_tca(
    order_id: UUID,
    request: Request,
    request_context: RequestContext = require_permission(Permission.ORDERS_CREATE),
    session: AsyncSession = Depends(get_db),
) -> TCAReport:
    """Manually trigger TCA computation for an order."""
    svc = _get_tca_service(request)
    report = await svc.compute_for_order(order_id, session=session)
    if report is None:
        raise HTTPException(
            400, f"Order {order_id} is not eligible for TCA (not filled or missing arrival price)"
        )
    return report


@router.get("/orders/tca/portfolio/{portfolio_id}", response_model=PortfolioTCAReport)
async def portfolio_tca(
    portfolio_id: UUID,
    request: Request,
    request_context: RequestContext = require_permission(Permission.ORDERS_READ),
    session: AsyncSession = Depends(get_read_db),
) -> PortfolioTCAReport:
    """Get aggregated TCA for all filled orders in a portfolio."""
    svc = _get_tca_service(request)
    return await svc.get_portfolio_report(portfolio_id, session=session)


@router.get("/orders/tca/summary", response_model=FundTCASummary)
async def fund_tca_summary(
    request: Request,
    request_context: RequestContext = require_permission(Permission.ORDERS_READ),
    days: int = Query(default=30, description="Number of days to include"),
) -> FundTCASummary:
    """Get high-level TCA summary for the current fund."""
    assert request_context.fund_slug is not None
    svc = _get_tca_service(request)
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    return await svc.get_fund_summary(request_context.fund_slug, start, end)
