"""Event handlers for position keeping — trade processing and mark-to-market."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import structlog

from app.modules.positions.aggregate import PositionAggregate
from app.modules.positions.interface import PositionEventType, TradeSide
from app.modules.positions.repository import CurrentPositionRepository, EventStoreRepository
from app.modules.positions.strategy import get_position_strategy
from app.shared.database import TenantSessionFactory
from app.shared.events import BaseEvent, EventBus
from app.shared.request_context import RequestContext
from app.shared.schema_registry import fund_topic
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
        currency: str = "USD",
    ) -> None:
        aggregate_id = f"{portfolio_id}:{instrument_id}"

        # Load current state from event store
        stored_events = await self._event_store.get_by_aggregate(aggregate_id)
        position = PositionAggregate.from_events(portfolio_id, instrument_id, stored_events)

        # Build trade event
        now = datetime.now(UTC)
        trade_id = str(uuid4())
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

        # Publish downstream events to fund-scoped topics
        for de in downstream_events:
            base = (
                "positions.changed"
                if de["event_type"] == PositionEventType.POSITION_CHANGED
                else "pnl.realized"
            )
            topic = fund_topic(ctx.fund_slug, base) if ctx.fund_slug else base
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
    """Revalues positions when prices update.

    Iterates over all active fund schemas to update every fund's positions.
    """

    def __init__(
        self,
        session_factory: TenantSessionFactory,
        event_bus: EventBus,
        get_fund_slugs: Callable[[], Awaitable[list[str]]],
    ) -> None:
        self._session_factory = session_factory
        self._event_bus = event_bus
        self._get_fund_slugs = get_fund_slugs

    async def handle_price_update(self, event: BaseEvent) -> None:
        instrument_id = event.data["instrument_id"]
        new_price = Decimal(event.data["mid"])
        strategy = get_position_strategy(AssetClass.EQUITY)

        for slug in await self._get_fund_slugs():
            await self._update_fund_positions(
                slug,
                instrument_id,
                new_price,
                strategy,
            )

    async def _update_fund_positions(
        self,
        fund_slug: str,
        instrument_id: str,
        new_price: Decimal,
        strategy: object,
    ) -> None:
        repo = CurrentPositionRepository(self._session_factory, fund_slug=fund_slug)
        positions = await repo.get_by_instrument(instrument_id)
        for pos in positions:
            new_market_value = strategy.market_value(pos.quantity, new_price)  # type: ignore[union-attr]
            new_unrealized = strategy.unrealized_pnl(pos.quantity, pos.cost_basis, new_price)  # type: ignore[union-attr]
            await repo.update_market_value(
                portfolio_id=pos.portfolio_id,
                instrument_id=instrument_id,
                market_price=new_price,
                market_value=new_market_value,
                unrealized_pnl=new_unrealized,
            )
