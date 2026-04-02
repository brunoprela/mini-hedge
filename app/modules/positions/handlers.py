"""Event handlers for position keeping — trade processing and mark-to-market."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import structlog

from app.modules.positions.aggregate import PositionAggregate
from app.modules.positions.interface import PositionEventType, TradeSide
from app.modules.positions.repository import CurrentPositionRepository, EventStoreRepository
from app.modules.positions.strategy import get_position_strategy
from app.shared.events import BaseEvent, EventBus
from app.shared.request_context import RequestContext
from app.shared.types import AssetClass

logger = structlog.get_logger()


class TradeHandler:
    """Processes trade events → updates position aggregate → updates read model."""

    def __init__(
        self,
        event_store: EventStoreRepository,
        position_repo: CurrentPositionRepository,
        event_bus: EventBus,
    ) -> None:
        self._event_store = event_store
        self._position_repo = position_repo
        self._event_bus = event_bus

    async def handle_trade(
        self,
        ctx: RequestContext,
        portfolio_id: UUID,
        instrument_id: str,
        side: TradeSide,
        quantity: Decimal,
        price: Decimal,
        trade_id: str,
        currency: str = "USD",
    ) -> None:
        aggregate_id = f"{portfolio_id}:{instrument_id}"

        # Load current state from event store
        stored_events = await self._event_store.get_events(aggregate_id)
        position = PositionAggregate.from_events(portfolio_id, instrument_id, stored_events)

        # Build trade event
        now = datetime.now(UTC)
        event_type = (
            PositionEventType.TRADE_BUY if side == TradeSide.BUY else PositionEventType.TRADE_SELL
        )
        trade_event = {
            "event_type": event_type,
            "timestamp": now.isoformat(),
            "data": {
                "portfolio_id": str(portfolio_id),
                "instrument_id": instrument_id,
                "side": side,
                "quantity": str(quantity),
                "price": str(price),
                "trade_id": trade_id,
                "currency": currency,
            },
        }

        # Apply to aggregate
        downstream_events = position.apply(trade_event)

        # Persist to event store
        seq = await self._event_store.get_next_sequence(aggregate_id)
        await self._event_store.append(
            aggregate_id=aggregate_id,
            event_type=trade_event["event_type"],
            event_data=trade_event["data"],
            sequence_number=seq,
            fund_id=ctx.fund_id,
        )

        # Update read model
        await self._position_repo.upsert(
            portfolio_id=portfolio_id,
            instrument_id=instrument_id,
            quantity=position.quantity,
            avg_cost=position.avg_cost,
            cost_basis=position.cost_basis,
            realized_pnl=position.realized_pnl,
            currency=currency,
            fund_id=ctx.fund_id,
        )

        # Publish downstream events
        for de in downstream_events:
            topic = (
                "positions.changed"
                if de["event_type"] == PositionEventType.POSITION_CHANGED
                else "pnl.realized"
            )
            await self._event_bus.publish(
                topic,
                BaseEvent(
                    event_type=de["event_type"],
                    data=de["data"],
                    actor_id=ctx.actor_id,
                    actor_type=ctx.actor_type.value,
                    fund_slug=ctx.fund_slug,
                ),
            )

        logger.info(
            "trade_processed",
            portfolio_id=str(portfolio_id),
            instrument_id=instrument_id,
            side=side,
            quantity=str(quantity),
            price=str(price),
        )


class MarkToMarketHandler:
    """Revalues positions when prices update."""

    def __init__(
        self,
        position_repo: CurrentPositionRepository,
        event_bus: EventBus,
    ) -> None:
        self._position_repo = position_repo
        self._event_bus = event_bus

    async def handle_price_update(self, event: BaseEvent) -> None:
        instrument_id = event.data["instrument_id"]
        new_price = Decimal(event.data["mid"])

        positions = await self._position_repo.get_by_instrument(instrument_id)
        # Use equity strategy for now; when positions store asset_class,
        # look up the correct strategy per position.
        strategy = get_position_strategy(AssetClass.EQUITY)

        for pos in positions:
            new_market_value = strategy.market_value(pos.quantity, new_price)
            new_unrealized = strategy.unrealized_pnl(pos.quantity, pos.cost_basis, new_price)

            await self._position_repo.update_market_value(
                portfolio_id=pos.portfolio_id,
                instrument_id=instrument_id,
                market_price=new_price,
                market_value=new_market_value,
                unrealized_pnl=new_unrealized,
            )
