"""Event handlers for position keeping — trade processing and mark-to-market."""

from datetime import UTC
from decimal import Decimal
from uuid import UUID

import structlog

from app.modules.positions.aggregate import PositionAggregate
from app.modules.positions.repository import CurrentPositionRepository, EventStoreRepository
from app.shared.events import BaseEvent, EventBus

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
        portfolio_id: UUID,
        instrument_id: str,
        side: str,
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
        from datetime import datetime

        now = datetime.now(UTC)
        trade_event = {
            "event_type": f"trade.{side}",
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
        )

        # Publish downstream events
        for de in downstream_events:
            topic = "positions.changed" if "position" in de["event_type"] else "pnl.updated"
            await self._event_bus.publish(
                topic,
                BaseEvent(event_type=de["event_type"], data=de["data"]),
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

        for pos in positions:
            new_market_value = pos.quantity * new_price
            new_unrealized = new_market_value - pos.cost_basis

            await self._position_repo.update_market_value(
                portfolio_id=pos.portfolio_id,
                instrument_id=instrument_id,
                market_price=new_price,
                market_value=new_market_value,
                unrealized_pnl=new_unrealized,
            )
