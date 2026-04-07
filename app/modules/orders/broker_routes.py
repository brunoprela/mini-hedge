"""FastAPI routes for multi-broker management and best execution reporting."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.modules.orders.interface import (
    BestExecutionReport,
    BrokerScorecard,
    CreateRoutingRuleRequest,
    RoutingRule,
)
from app.shared.auth import Permission, require_permission
from app.shared.database import get_db

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.orders.best_execution import BestExecutionService
    from app.modules.orders.broker_registry import BrokerRegistry
    from app.modules.orders.routing_repository import RoutingRepository
    from app.modules.orders.scorecard_service import ScorecardService
    from app.shared.request_context import RequestContext

router = APIRouter(tags=["brokers"])


def _get_broker_registry(request: Request) -> BrokerRegistry:
    registry = getattr(request.app.state, "broker_registry", None)
    if registry is None:
        raise HTTPException(503, "BrokerRegistry not initialized")
    return cast("BrokerRegistry", registry)


def _get_scorecard_service(request: Request) -> ScorecardService:
    svc = getattr(request.app.state, "scorecard_service", None)
    if svc is None:
        raise HTTPException(503, "ScorecardService not initialized")
    return cast("ScorecardService", svc)


def _get_best_execution_service(request: Request) -> BestExecutionService:
    svc = getattr(request.app.state, "best_execution_service", None)
    if svc is None:
        raise HTTPException(503, "BestExecutionService not initialized")
    return cast("BestExecutionService", svc)


def _get_routing_repo(request: Request) -> RoutingRepository:
    repo = getattr(request.app.state, "routing_repo", None)
    if repo is None:
        raise HTTPException(503, "RoutingRepository not initialized")
    return cast("RoutingRepository", repo)


# --- Broker listing ---


@router.get("/brokers")
async def list_brokers(
    request: Request,
    request_context: RequestContext = require_permission(Permission.ORDERS_READ),
) -> list[dict[str, Any]]:
    """List registered brokers."""
    registry = _get_broker_registry(request)
    return [
        {"broker_id": bid, "is_default": bid == registry.default_broker_id}
        for bid in registry.list_broker_ids()
    ]


@router.get("/brokers/scorecards", response_model=list[BrokerScorecard])
async def list_scorecards(
    request: Request,
    request_context: RequestContext = require_permission(Permission.ORDERS_READ),
) -> list[BrokerScorecard]:
    """Get scorecards for all brokers."""
    assert request_context.fund_slug is not None
    svc = _get_scorecard_service(request)
    return await svc.get_all_scorecards(request_context.fund_slug)


@router.get("/brokers/{broker_id}/scorecard", response_model=BrokerScorecard)
async def get_scorecard(
    broker_id: str,
    request: Request,
    request_context: RequestContext = require_permission(Permission.ORDERS_READ),
) -> BrokerScorecard:
    """Get scorecard for a specific broker."""
    assert request_context.fund_slug is not None
    svc = _get_scorecard_service(request)
    sc = await svc.get_scorecard(broker_id, request_context.fund_slug)
    if sc is None:
        raise HTTPException(404, f"No scorecard for broker {broker_id}")
    return sc


# --- Routing rules ---


@router.get("/routing-rules", response_model=list[RoutingRule])
async def list_routing_rules(
    request: Request,
    request_context: RequestContext = require_permission(Permission.ORDERS_READ),
) -> list[RoutingRule]:
    """List routing rules for the current fund."""
    assert request_context.fund_slug is not None
    repo = _get_routing_repo(request)
    records = await repo.get_rules_for_fund(request_context.fund_slug)
    return [
        RoutingRule(
            id=UUID(r.id),
            fund_slug=r.fund_slug,
            strategy=r.strategy,
            instrument_class=r.instrument_class,
            min_size=r.min_size,
            max_size=r.max_size,
            preferred_broker_id=r.preferred_broker_id,
            priority=r.priority,
            is_active=r.is_active,
        )
        for r in records
    ]


@router.post("/routing-rules", response_model=RoutingRule, status_code=201)
async def create_routing_rule(
    body: CreateRoutingRuleRequest,
    request: Request,
    request_context: RequestContext = require_permission(Permission.ORDERS_CREATE),
    session: AsyncSession = Depends(get_db),
) -> RoutingRule:
    """Create a new routing rule."""
    from uuid import uuid4

    from app.modules.orders.models import RoutingRuleRecord

    repo = _get_routing_repo(request)
    record = RoutingRuleRecord(
        id=str(uuid4()),
        fund_slug=body.fund_slug,
        strategy=body.strategy,
        instrument_class=body.instrument_class,
        min_size=body.min_size,
        max_size=body.max_size,
        preferred_broker_id=body.preferred_broker_id,
        priority=body.priority,
    )
    saved = await repo.save_rule(record, session=session)
    return RoutingRule(
        id=UUID(saved.id),
        fund_slug=saved.fund_slug,
        strategy=saved.strategy,
        instrument_class=saved.instrument_class,
        min_size=saved.min_size,
        max_size=saved.max_size,
        preferred_broker_id=saved.preferred_broker_id,
        priority=saved.priority,
        is_active=saved.is_active,
    )


@router.delete("/routing-rules/{rule_id}")
async def delete_routing_rule(
    rule_id: UUID,
    request: Request,
    request_context: RequestContext = require_permission(Permission.ORDERS_CREATE),
) -> dict[str, bool]:
    """Delete a routing rule."""
    repo = _get_routing_repo(request)
    deleted = await repo.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(404, f"Rule {rule_id} not found")
    return {"deleted": True}


# --- Best execution reports ---


@router.get("/best-execution/report", response_model=BestExecutionReport)
async def best_execution_report(
    request: Request,
    request_context: RequestContext = require_permission(Permission.ORDERS_READ),
    days: int = Query(default=30, description="Number of days to include"),
) -> BestExecutionReport:
    """Generate a best execution report for the fund."""
    assert request_context.fund_slug is not None
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
    assert request_context.fund_slug is not None
    svc = _get_best_execution_service(request)
    return await svc.get_order_execution_detail(order_id, request_context.fund_slug)
