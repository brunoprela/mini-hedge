"""FastAPI routes for position keeping."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.modules.positions.interface import Position, TradeRequest
from app.modules.positions.service import PositionService
from app.shared.auth import Permission, require_permission
from app.shared.fga import ParamSource, require_access
from app.shared.fga_resources import Portfolio
from app.shared.request_context import RequestContext

router = APIRouter(prefix="/portfolios", tags=["positions"])

_service: PositionService | None = None


def init_routes(service: PositionService) -> None:
    global _service
    _service = service


def _get_service() -> PositionService:
    assert _service is not None, "PositionService not initialized"
    return _service


@router.get("/{portfolio_id}/positions", response_model=list[Position])
async def list_positions(
    portfolio_id: UUID,
    ctx: RequestContext = require_permission(Permission.POSITIONS_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
) -> list[Position]:
    return await _get_service().get_portfolio_positions(portfolio_id)


@router.get(
    "/{portfolio_id}/positions/{instrument_id}",
    response_model=Position,
)
async def get_position(
    portfolio_id: UUID,
    instrument_id: str,
    ctx: RequestContext = require_permission(Permission.POSITIONS_READ),
    _access: None = require_access(Portfolio.relation("can_view")),
) -> Position:
    position = await _get_service().get_position(portfolio_id, instrument_id.upper())
    if position is None:
        raise HTTPException(
            status_code=404,
            detail=f"No position for {instrument_id} in portfolio {portfolio_id}",
        )
    return position


@router.post("/trades", response_model=Position, status_code=201)
async def execute_trade(
    request: TradeRequest,
    ctx: RequestContext = require_permission(Permission.TRADES_EXECUTE),
    _access: None = require_access(Portfolio.relation("can_trade"), source=ParamSource.BODY),
) -> Position:
    if request.side not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="side must be 'buy' or 'sell'")
    if request.quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")
    if request.price <= 0:
        raise HTTPException(status_code=400, detail="price must be positive")
    return await _get_service().execute_trade(request)
