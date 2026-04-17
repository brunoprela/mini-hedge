"""FastAPI routes for position keeping."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform.dependencies import get_fund_repo, get_portfolio_repo
from app.modules.platform.repositories import FundRepository, PortfolioRepository
from app.modules.positions.dependencies import get_position_service
from app.modules.positions.interfaces import (
    FundAggregate,
    PortfolioSummary,
    Position,
    PositionLot,
    TradeRequest,
)
from app.modules.positions.services import PositionService
from app.shared.auth import Permission, require_permission
from app.shared.auth.request_context import RequestContext
from app.shared.database import get_db, get_read_db
from app.shared.fga import ParamSource, require_access
from app.shared.fga.resources import Portfolio

router = APIRouter(prefix="/portfolios", tags=["positions"])


@router.get("/aggregate", response_model=FundAggregate)
async def get_fund_aggregate(
    request_context: RequestContext = require_permission(Permission.POSITIONS_READ),
    position_service: PositionService = Depends(get_position_service),
    fund_repo: FundRepository = Depends(get_fund_repo),
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repo),
    session: AsyncSession = Depends(get_read_db),
) -> FundAggregate:
    """Aggregate cross-portfolio KPIs for the current fund."""
    if not request_context.fund_slug:
        raise HTTPException(status_code=400, detail="Fund context required")
    fund = await fund_repo.get_by_slug(request_context.fund_slug, session=session)
    if fund is None:
        raise HTTPException(status_code=404, detail="Fund not found")
    portfolios = await portfolio_repo.get_by_fund(fund.id, session=session)

    total_aum = Decimal(0)
    total_realized = Decimal(0)
    total_unrealized = Decimal(0)
    total_positions = 0
    for portfolio in portfolios:
        summary = await position_service.get_portfolio_summary(
            UUID(portfolio.id), session=session
        )
        total_aum += summary.total_market_value
        total_realized += summary.total_realized_pnl
        total_unrealized += summary.total_unrealized_pnl
        total_positions += summary.position_count

    return FundAggregate(
        total_aum=total_aum,
        total_realized_pnl=total_realized,
        total_unrealized_pnl=total_unrealized,
        portfolio_count=len(portfolios),
        total_positions=total_positions,
    )


@router.get("/{portfolio_id}/positions", response_model=list[Position])
async def list_positions(
    portfolio_id: UUID,
    request_context: RequestContext = require_permission(Permission.POSITIONS_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    position_service: PositionService = Depends(get_position_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[Position]:
    return await position_service.get_by_portfolio(portfolio_id, session=session)


@router.get(
    "/{portfolio_id}/positions/{instrument_id}",
    response_model=Position,
)
async def get_position(
    portfolio_id: UUID,
    instrument_id: str,
    request_context: RequestContext = require_permission(Permission.POSITIONS_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    position_service: PositionService = Depends(get_position_service),
    session: AsyncSession = Depends(get_read_db),
) -> Position:
    position = await position_service.get_position(
        portfolio_id, instrument_id.upper(), session=session
    )
    if position is None:
        raise HTTPException(
            status_code=404,
            detail=f"No position for {instrument_id} in portfolio {portfolio_id}",
        )
    return position


@router.get(
    "/{portfolio_id}/positions/{instrument_id}/lots",
    response_model=list[PositionLot],
)
async def get_lots(
    portfolio_id: UUID,
    instrument_id: str,
    request_context: RequestContext = require_permission(Permission.POSITIONS_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    position_service: PositionService = Depends(get_position_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[PositionLot]:
    return await position_service.get_lots(portfolio_id, instrument_id.upper(), session=session)


@router.get("/{portfolio_id}/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(
    portfolio_id: UUID,
    request_context: RequestContext = require_permission(Permission.POSITIONS_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    position_service: PositionService = Depends(get_position_service),
    session: AsyncSession = Depends(get_read_db),
) -> PortfolioSummary:
    return await position_service.get_portfolio_summary(portfolio_id, session=session)


@router.post("/trades", response_model=Position, status_code=201)
async def execute_trade(
    trade_request: TradeRequest,
    request_context: RequestContext = require_permission(Permission.TRADES_EXECUTE),
    _access: None = require_access(Portfolio.relation("can_trade"), source=ParamSource.BODY),
    position_service: PositionService = Depends(get_position_service),
    session: AsyncSession = Depends(get_db),
) -> Position:
    if trade_request.quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")
    if trade_request.price <= 0:
        raise HTTPException(status_code=400, detail="price must be positive")
    return await position_service.execute_trade(trade_request, request_context, session=session)
