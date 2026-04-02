"""Position keeping business logic — implements PositionReader protocol."""

from uuid import UUID

from app.modules.positions.handlers import TradeHandler
from app.modules.positions.interface import Position, TradeRequest
from app.modules.positions.models import CurrentPositionRecord
from app.modules.positions.repository import CurrentPositionRepository
from app.shared.request_context import RequestContext


def _to_position(record: CurrentPositionRecord) -> Position:
    return Position(
        portfolio_id=UUID(record.portfolio_id),
        instrument_id=record.instrument_id,
        quantity=record.quantity,
        avg_cost=record.avg_cost,
        cost_basis=record.cost_basis,
        market_price=record.market_price,
        market_value=record.market_value,
        unrealized_pnl=record.unrealized_pnl,
        currency=record.currency,
        last_updated=record.last_updated,
    )


class PositionService:
    """Implements PositionReader protocol and trade entry."""

    def __init__(
        self,
        position_repo: CurrentPositionRepository,
        trade_handler: TradeHandler,
    ) -> None:
        self._position_repo = position_repo
        self._trade_handler = trade_handler

    async def get_position(
        self,
        portfolio_id: UUID,
        instrument_id: str,
    ) -> Position | None:
        record = await self._position_repo.get_position(portfolio_id, instrument_id)
        if record is None:
            return None
        return _to_position(record)

    async def get_by_portfolio(
        self,
        portfolio_id: UUID,
    ) -> list[Position]:
        records = await self._position_repo.get_by_portfolio(portfolio_id)
        return [_to_position(r) for r in records]

    async def execute_trade(self, request: TradeRequest, ctx: RequestContext) -> Position:
        """Process a trade and return the updated position."""
        await self._trade_handler.handle_trade(
            ctx=ctx,
            portfolio_id=request.portfolio_id,
            instrument_id=request.instrument_id.upper(),
            side=request.side,
            quantity=request.quantity,
            price=request.price,
            currency=request.currency,
        )

        # Return updated position
        position = await self.get_position(request.portfolio_id, request.instrument_id.upper())
        if position is None:
            raise RuntimeError(f"Position read-back failed after trade for {request.instrument_id}")
        return position
