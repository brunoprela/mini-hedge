"""FastAPI routes for cash management."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cash_management.cash_management_service import CashManagementService
from app.modules.cash_management.dependencies import get_cash_service
from app.modules.cash_management.interface import (
    CashBalance,
    CashProjection,
    SettlementLadder,
    SettlementRecord,
)
from app.shared.auth import Permission, require_permission
from app.shared.database import get_db
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
    request_context: RequestContext = require_permission(Permission.CASH_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    cash_management_service: CashManagementService = Depends(get_cash_service),
    session: AsyncSession = Depends(get_db),
) -> list[CashBalance]:
    return await cash_management_service.get_balances(portfolio_id, session=session)


@router.get(
    "/{portfolio_id}/settlements",
    response_model=list[SettlementRecord],
)
async def get_pending_settlements(
    portfolio_id: UUID,
    request_context: RequestContext = require_permission(Permission.CASH_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    cash_management_service: CashManagementService = Depends(get_cash_service),
    session: AsyncSession = Depends(get_db),
) -> list[SettlementRecord]:
    return await cash_management_service.get_pending_settlements(portfolio_id, session=session)


@router.get(
    "/{portfolio_id}/ladder",
    response_model=SettlementLadder,
)
async def get_settlement_ladder(
    portfolio_id: UUID,
    horizon_days: int = Query(default=10, ge=1, le=90),
    request_context: RequestContext = require_permission(Permission.CASH_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    cash_management_service: CashManagementService = Depends(get_cash_service),
    session: AsyncSession = Depends(get_db),
) -> SettlementLadder:
    return await cash_management_service.get_settlement_ladder(
        portfolio_id, horizon_days, session=session
    )


@router.get(
    "/{portfolio_id}/projection",
    response_model=CashProjection,
)
async def get_cash_projection(
    portfolio_id: UUID,
    horizon_days: int = Query(default=30, ge=1, le=365),
    request_context: RequestContext = require_permission(Permission.CASH_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    cash_management_service: CashManagementService = Depends(get_cash_service),
    session: AsyncSession = Depends(get_db),
) -> CashProjection:
    return await cash_management_service.get_projection(portfolio_id, horizon_days, session=session)
