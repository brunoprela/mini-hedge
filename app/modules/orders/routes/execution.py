"""FastAPI routes for best execution reporting."""

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from app.modules.orders.core.best_execution import BestExecutionService
from app.modules.orders.interfaces import BestExecutionReport
from app.shared.auth import Permission, require_permission
from app.shared.auth.request_context import RequestContext

router = APIRouter(tags=["brokers"])


def _get_best_execution_service(request: Request) -> BestExecutionService:
    svc = getattr(request.app.state, "best_execution_service", None)
    if svc is None:
        raise HTTPException(503, "BestExecutionService not initialized")
    return cast("BestExecutionService", svc)


@router.get("/best-execution/report", response_model=BestExecutionReport)
async def best_execution_report(
    request: Request,
    request_context: RequestContext = require_permission(Permission.ORDERS_READ),
    days: int = Query(default=30, description="Number of days to include"),
) -> BestExecutionReport:
    """Generate a best execution report for the fund."""
    if request_context.fund_slug is None:
        raise HTTPException(400, "fund_slug is required")
    svc = _get_best_execution_service(request)
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    return await svc.generate_report(request_context.fund_slug, start, end)


@router.get("/best-execution/orders/{order_id}")
async def order_execution_detail(
    order_id: UUID,
    request: Request,
    request_context: RequestContext = require_permission(Permission.ORDERS_READ),
) -> dict[str, Any]:
    """Get detailed execution analysis for a single order."""
    if request_context.fund_slug is None:
        raise HTTPException(400, "fund_slug is required")
    svc = _get_best_execution_service(request)
    return await svc.get_order_execution_detail(order_id, request_context.fund_slug)
