"""FastAPI routes for position keeping."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from app.modules.positions.interface import Position, TradeRequest
from app.modules.positions.service import PositionService
from app.shared.auth import Permission, require_permission
from app.shared.fga import ParamSource, require_access
from app.shared.fga_resources import Portfolio
from app.shared.request_context import RequestContext

router = APIRouter(prefix="/portfolios", tags=["positions"])


def _get_service(request: Request) -> PositionService:
    service: PositionService | None = getattr(request.app.state, "position_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="PositionService not initialized")
    return service


@router.get("/{portfolio_id}/positions", response_model=list[Position])
async def list_positions(
    request: Request,
    portfolio_id: UUID,
    ctx: RequestContext = require_permission(Permission.POSITIONS_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
) -> list[Position]:
    return await _get_service(request).get_portfolio_positions(portfolio_id)


@router.get(
    "/{portfolio_id}/positions/{instrument_id}",
    response_model=Position,
)
async def get_position(
    request: Request,
    portfolio_id: UUID,
    instrument_id: str,
    ctx: RequestContext = require_permission(Permission.POSITIONS_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
) -> Position:
    position = await _get_service(request).get_position(portfolio_id, instrument_id.upper())
    if position is None:
        raise HTTPException(
            status_code=404,
            detail=f"No position for {instrument_id} in portfolio {portfolio_id}",
        )
    return position


@router.post("/trades", response_model=Position, status_code=201)
async def execute_trade(
    request: Request,
    trade_request: TradeRequest,
    ctx: RequestContext = require_permission(Permission.TRADES_EXECUTE),
    _access: None = require_access(Portfolio.relation("can_trade"), source=ParamSource.BODY),
) -> Position:
    if trade_request.quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")
    if trade_request.price <= 0:
        raise HTTPException(status_code=400, detail="price must be positive")
    return await _get_service(request).execute_trade(trade_request)
