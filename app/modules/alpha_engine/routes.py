"""FastAPI routes for alpha engine."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.alpha_engine.alpha_service import AlphaService
from app.modules.alpha_engine.dependencies import get_alpha_service
from app.modules.alpha_engine.interface import (
    HypotheticalTrade,
    OptimizationObjective,
    OptimizationResult,
    OrderIntent,
    ScenarioRun,
    WhatIfResult,
)
from app.shared.auth import Permission, require_permission
from app.shared.database import get_db
from app.shared.fga import require_access
from app.shared.fga_resources import Portfolio
from app.shared.request_context import RequestContext

router = APIRouter(prefix="/alpha", tags=["alpha"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class TradeInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    instrument_id: str
    side: str
    quantity: Decimal
    price: Decimal


class WhatIfRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenario_name: str
    trades: list[TradeInput]


class OptimizeRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    objective: OptimizationObjective = OptimizationObjective.MAX_SHARPE


# ---------------------------------------------------------------------------
# What-if routes
# ---------------------------------------------------------------------------


@router.post("/{portfolio_id}/what-if", response_model=WhatIfResult)
async def run_what_if(
    portfolio_id: UUID,
    body: WhatIfRequest,
    request_context: RequestContext = require_permission(Permission.ALPHA_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    alpha_service: AlphaService = Depends(get_alpha_service),
    session: AsyncSession = Depends(get_db),
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
    return await alpha_service.run_what_if(
        portfolio_id, body.scenario_name, trades, session=session
    )


@router.get(
    "/{portfolio_id}/scenarios",
    response_model=list[ScenarioRun],
)
async def list_scenarios(
    portfolio_id: UUID,
    request_context: RequestContext = require_permission(Permission.ALPHA_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    alpha_service: AlphaService = Depends(get_alpha_service),
    session: AsyncSession = Depends(get_db),
) -> list[ScenarioRun]:
    return await alpha_service.get_scenarios(portfolio_id, session=session)


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
    request_context: RequestContext = require_permission(Permission.ALPHA_WRITE),
    _access: None = require_access(Portfolio.relation("can_trade")),
    alpha_service: AlphaService = Depends(get_alpha_service),
    session: AsyncSession = Depends(get_db),
) -> OptimizationResult:
    return await alpha_service.optimize(portfolio_id, body.objective, session=session)


@router.get(
    "/{portfolio_id}/optimizations",
    response_model=list[OptimizationResult],
)
async def list_optimizations(
    portfolio_id: UUID,
    request_context: RequestContext = require_permission(Permission.ALPHA_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    alpha_service: AlphaService = Depends(get_alpha_service),
    session: AsyncSession = Depends(get_db),
) -> list[OptimizationResult]:
    return await alpha_service.get_optimizations(portfolio_id, session=session)


# ---------------------------------------------------------------------------
# Order intent routes
# ---------------------------------------------------------------------------


@router.get(
    "/{portfolio_id}/intents",
    response_model=list[OrderIntent],
)
async def list_order_intents(
    portfolio_id: UUID,
    request_context: RequestContext = require_permission(Permission.ALPHA_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    alpha_service: AlphaService = Depends(get_alpha_service),
    session: AsyncSession = Depends(get_db),
) -> list[OrderIntent]:
    return await alpha_service.get_order_intents(portfolio_id, session=session)


@router.post("/{portfolio_id}/intents/{intent_id}/approve")
async def approve_intent(
    portfolio_id: UUID,
    intent_id: str,
    request_context: RequestContext = require_permission(Permission.ALPHA_WRITE),
    _access: None = require_access(Portfolio.relation("can_trade")),
    alpha_service: AlphaService = Depends(get_alpha_service),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await alpha_service.approve_intent(intent_id, session=session)
    return {"status": "approved"}


@router.post("/{portfolio_id}/intents/{intent_id}/cancel")
async def cancel_intent(
    portfolio_id: UUID,
    intent_id: str,
    request_context: RequestContext = require_permission(Permission.ALPHA_WRITE),
    _access: None = require_access(Portfolio.relation("can_trade")),
    alpha_service: AlphaService = Depends(get_alpha_service),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await alpha_service.cancel_intent(intent_id, session=session)
    return {"status": "cancelled"}
