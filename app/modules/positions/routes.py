"""FastAPI routes for position keeping."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.positions.dependencies import get_position_service
from app.modules.positions.interface import PortfolioSummary, Position, PositionLot, TradeRequest
from app.modules.positions.position_service import PositionService
from app.shared.auth import Permission, require_permission
from app.shared.database import get_db
from app.shared.fga import ParamSource, require_access
from app.shared.fga_resources import Portfolio
from app.shared.request_context import RequestContext

router = APIRouter(prefix="/portfolios", tags=["positions"])


@router.get("/{portfolio_id}/positions", response_model=list[Position])
async def list_positions(
    portfolio_id: UUID,
    request_context: RequestContext = require_permission(Permission.POSITIONS_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    position_service: PositionService = Depends(get_position_service),
    session: AsyncSession = Depends(get_db),
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
    session: AsyncSession = Depends(get_db),
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
    session: AsyncSession = Depends(get_db),
) -> list[PositionLot]:
    return await position_service.get_lots(portfolio_id, instrument_id.upper(), session=session)


@router.get("/{portfolio_id}/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(
    portfolio_id: UUID,
    request_context: RequestContext = require_permission(Permission.POSITIONS_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
    position_service: PositionService = Depends(get_position_service),
    session: AsyncSession = Depends(get_db),
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
