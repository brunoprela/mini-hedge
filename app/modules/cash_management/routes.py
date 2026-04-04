"""FastAPI routes for cash management."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.modules.cash_management.dependencies import get_cash_service
from app.modules.cash_management.interface import (
    CashBalance,
    CashProjection,
    SettlementLadder,
    SettlementRecord,
)
from app.modules.cash_management.service import CashManagementService
from app.shared.auth import Permission, require_permission
from app.shared.fga import require_access
from app.shared.fga_resources import Portfolio
from app.shared.request_context import RequestContext

router = APIRouter(prefix="/cash", tags=["cash"])


@router.get(
    "/{portfolio_id}/balances",
    response_model=list[CashBalance],
)
async def get_cash_balances(
    portfolio_id: UUID,
    ctx: RequestContext = require_permission(Permission.CASH_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: CashManagementService = Depends(get_cash_service),
) -> list[CashBalance]:
    return await service.get_balances(portfolio_id)


@router.get(
    "/{portfolio_id}/settlements",
    response_model=list[SettlementRecord],
)
async def get_pending_settlements(
    portfolio_id: UUID,
    ctx: RequestContext = require_permission(Permission.CASH_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: CashManagementService = Depends(get_cash_service),
) -> list[SettlementRecord]:
    return await service.get_pending_settlements(portfolio_id)


@router.get(
    "/{portfolio_id}/ladder",
    response_model=SettlementLadder,
)
async def get_settlement_ladder(
    portfolio_id: UUID,
    horizon_days: int = Query(default=10, ge=1, le=90),
    ctx: RequestContext = require_permission(Permission.CASH_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: CashManagementService = Depends(get_cash_service),
) -> SettlementLadder:
    return await service.get_settlement_ladder(portfolio_id, horizon_days)


@router.get(
    "/{portfolio_id}/projection",
    response_model=CashProjection,
)
async def get_cash_projection(
    portfolio_id: UUID,
    horizon_days: int = Query(default=30, ge=1, le=365),
    ctx: RequestContext = require_permission(Permission.CASH_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    service: CashManagementService = Depends(get_cash_service),
) -> CashProjection:
    return await service.get_projection(portfolio_id, horizon_days)
