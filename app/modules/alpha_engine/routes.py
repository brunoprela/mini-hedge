"""FastAPI routes for alpha engine."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.modules.alpha_engine.dependencies import get_alpha_service
from app.modules.alpha_engine.interface import (
    HypotheticalTrade,
    OptimizationObjective,
    OptimizationResult,
    OrderIntent,
    ScenarioRun,
    WhatIfResult,
)
from app.modules.alpha_engine.service import AlphaService
from app.shared.auth import Permission, require_permission
from app.shared.fga import require_access
from app.shared.fga_resources import Portfolio
from app.shared.request_context import RequestContext

router = APIRouter(prefix="/alpha", tags=["alpha"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class TradeInput(BaseModel):
    instrument_id: str
    side: str
    quantity: Decimal
    price: Decimal


class WhatIfRequest(BaseModel):
    scenario_name: str
    trades: list[TradeInput]


class OptimizeRequest(BaseModel):
    objective: OptimizationObjective = OptimizationObjective.MAX_SHARPE


# ---------------------------------------------------------------------------
# What-if routes
# ---------------------------------------------------------------------------


@router.post("/{portfolio_id}/what-if", response_model=WhatIfResult)
async def run_what_if(
    portfolio_id: UUID,
    body: WhatIfRequest,
    ctx: RequestContext = require_permission(Permission.ALPHA_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: AlphaService = Depends(get_alpha_service),
) -> WhatIfResult:
    trades = [
        HypotheticalTrade(
            instrument_id=t.instrument_id,
            side=t.side,
            quantity=t.quantity,
            price=t.price,
        )
        for t in body.trades
    ]
    return await service.run_what_if(portfolio_id, body.scenario_name, trades)


@router.get(
    "/{portfolio_id}/scenarios",
    response_model=list[ScenarioRun],
)
async def list_scenarios(
    portfolio_id: UUID,
    ctx: RequestContext = require_permission(Permission.ALPHA_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: AlphaService = Depends(get_alpha_service),
) -> list[ScenarioRun]:
    return await service.get_scenarios(portfolio_id)


# ---------------------------------------------------------------------------
# Optimization routes
# ---------------------------------------------------------------------------


@router.post(
    "/{portfolio_id}/optimize",
    response_model=OptimizationResult,
)
async def optimize_portfolio(
    portfolio_id: UUID,
    body: OptimizeRequest,
    ctx: RequestContext = require_permission(Permission.ALPHA_WRITE),
    _access: None = require_access(Portfolio.relation("can_trade")),
    service: AlphaService = Depends(get_alpha_service),
) -> OptimizationResult:
    return await service.optimize(portfolio_id, body.objective)


@router.get(
    "/{portfolio_id}/optimizations",
    response_model=list[OptimizationResult],
)
async def list_optimizations(
    portfolio_id: UUID,
    ctx: RequestContext = require_permission(Permission.ALPHA_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: AlphaService = Depends(get_alpha_service),
) -> list[OptimizationResult]:
    return await service.get_optimizations(portfolio_id)


# ---------------------------------------------------------------------------
# Order intent routes
# ---------------------------------------------------------------------------


@router.get(
    "/{portfolio_id}/intents",
    response_model=list[OrderIntent],
)
async def list_order_intents(
    portfolio_id: UUID,
    ctx: RequestContext = require_permission(Permission.ALPHA_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: AlphaService = Depends(get_alpha_service),
) -> list[OrderIntent]:
    return await service.get_order_intents(portfolio_id)


@router.post("/{portfolio_id}/intents/{intent_id}/approve")
async def approve_intent(
    portfolio_id: UUID,
    intent_id: str,
    ctx: RequestContext = require_permission(Permission.ALPHA_WRITE),
    _access: None = require_access(Portfolio.relation("can_trade")),
    service: AlphaService = Depends(get_alpha_service),
) -> dict[str, str]:
    await service.approve_intent(intent_id)
    return {"status": "approved"}


@router.post("/{portfolio_id}/intents/{intent_id}/cancel")
async def cancel_intent(
    portfolio_id: UUID,
    intent_id: str,
    ctx: RequestContext = require_permission(Permission.ALPHA_WRITE),
    _access: None = require_access(Portfolio.relation("can_trade")),
    service: AlphaService = Depends(get_alpha_service),
) -> dict[str, str]:
    await service.cancel_intent(intent_id)
    return {"status": "cancelled"}
