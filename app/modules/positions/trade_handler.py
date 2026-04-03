"""Command handler for trade execution — processes trades into the position aggregate."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog
from sqlalchemy.exc import IntegrityError

from app.modules.positions.aggregate import PositionAggregate
from app.modules.positions.event_store import EventStoreRepository
from app.modules.positions.interface import (
    DownstreamEvent,
    PnLMarkToMarket,
    PnLRealized,
    PositionChanged,
    PositionEventType,
    TradeEvent,
    TradeEventData,
    TradeSide,
)
from app.shared.events import BaseEvent, EventBus
from app.shared.schema_registry import fund_topic

if TYPE_CHECKING:
    from app.modules.positions.position_projector import PositionProjector
    from app.shared.database import TenantSessionFactory
    from app.shared.request_context import RequestContext

logger = structlog.get_logger()


class TradeHandler:
    """Processes trade events → updates position aggregate → projects read model."""

    def __init__(
        self,
        session_factory: TenantSessionFactory,
        event_store: EventStoreRepository,
        projector: PositionProjector,
        event_bus: EventBus,
    ) -> None:
        self._session_factory = session_factory
        self._event_store = event_store
        self._projector = projector
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
        idempotency_key: str | None = None,
    ) -> None:
        aggregate_id = f"{portfolio_id}:{instrument_id}"

        # Build typed trade event
        now = datetime.now(UTC)
        trade_id = uuid4()
        event_type = (
            PositionEventType.TRADE_BUY if side == TradeSide.BUY else PositionEventType.TRADE_SELL
        )
        trade_event = TradeEvent(
            event_type=event_type,
            timestamp=now,
            data=TradeEventData(
                portfolio_id=portfolio_id,
                instrument_id=instrument_id,
                side=side,
                quantity=quantity,
                price=price,
                trade_id=trade_id,
                currency=currency,
            ),
        )

        # Build metadata for the event store (includes idempotency key if present)
        event_metadata: dict[str, str] = {}
        if idempotency_key:
            event_metadata["idempotency_key"] = idempotency_key

        # Single transaction: load events, append new event, project read model.
        # Retry on sequence_number conflict (concurrent write to same aggregate).
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                async with self._session_factory() as session:
                    # Idempotency check — reject duplicate if key already exists
                    if idempotency_key and await self._event_store.has_idempotency_key(
                        idempotency_key, session=session,
                    ):
                        logger.info(
                            "trade_idempotent_duplicate",
                            idempotency_key=idempotency_key,
                        )
                        return

                    # Load current state from event store
                    stored_events = await self._event_store.get_by_aggregate(
                        aggregate_id, session=session
                    )
                    position = PositionAggregate.from_events(
                        portfolio_id, instrument_id, stored_events
                    )

                    # Apply to aggregate (pure logic, no I/O)
                    downstream_events = position.apply(trade_event)

                    # Persist event to event store
                    await self._event_store.append(
                        aggregate_id=aggregate_id,
                        event_type=trade_event.event_type,
                        event_data=EventStoreRepository.serialize(trade_event),
                        session=session,
                        metadata=event_metadata,
                    )

                    # Project read model in same transaction
                    await self._projector.project(position, session=session, currency=currency)

                    await session.commit()
                break  # success
            except IntegrityError:
                if attempt == max_retries:
                    logger.error(
                        "trade_conflict_exhausted",
                        aggregate_id=aggregate_id,
                        attempts=max_retries,
                    )
                    raise
                logger.warning(
                    "trade_conflict_retry",
                    aggregate_id=aggregate_id,
                    attempt=attempt,
                )

        # Publish raw trade event to trades.executed topic
        trade_data = asdict(trade_event.data)
        serialized_trade = {k: str(v) for k, v in trade_data.items()}
        trade_topic = (
            fund_topic(ctx.fund_slug, "trades.executed") if ctx.fund_slug else "trades.executed"
        )
        await self._event_bus.publish(
            trade_topic,
            BaseEvent(
                event_type=trade_event.event_type,
                data=serialized_trade,
                actor_id=ctx.actor_id,
                actor_type=ctx.actor_type.value,
                fund_slug=ctx.fund_slug,
            ),
        )

        # Publish downstream events to fund-scoped topics
        await self._publish_downstream(ctx, downstream_events)

        logger.info(
            "trade_processed",
            portfolio_id=str(portfolio_id),
            instrument_id=instrument_id,
            side=side,
            quantity=str(quantity),
            price=str(price),
        )

    async def _publish_downstream(
        self,
        ctx: RequestContext,
        downstream_events: list[DownstreamEvent],
    ) -> None:
        for de in downstream_events:
            match de:
                case PositionChanged():
                    base_topic = "positions.changed"
                case PnLRealized() | PnLMarkToMarket():
                    base_topic = "pnl.updated"
                case _:
                    raise ValueError(f"Unknown downstream event type: {type(de).__name__}")

            topic = fund_topic(ctx.fund_slug, base_topic) if ctx.fund_slug else base_topic
            data = asdict(de.data)
            # Serialize UUIDs and Decimals to strings for the event bus
            serialized_data = {k: str(v) for k, v in data.items()}

            await self._event_bus.publish(
                topic,
                BaseEvent(
                    event_type=de.event_type,
                    data=serialized_data,
                    actor_id=ctx.actor_id,
                    actor_type=ctx.actor_type.value,
                    fund_slug=ctx.fund_slug,
                ),
            )
