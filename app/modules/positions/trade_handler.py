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
    """Processes trade events → updates position aggregate → projects read model.

    Two entry points:

    * ``handle_trade`` — called directly (e.g. PositionService.record_trade).
      Publishes **both** ``trades.executed`` and downstream events
      (``positions.changed``, ``pnl.updated``).

    * ``handle_trade_event`` — called as a Kafka subscriber on
      ``trades.executed``.  Publishes **only** downstream events (the
      trade event already exists — re-publishing would loop).
    """

    def __init__(
        self,
        *,
        session_factory: TenantSessionFactory,
        event_store: EventStoreRepository,
        projector: PositionProjector,
        event_bus: EventBus,
    ) -> None:
        self._sf = session_factory
        self._event_store = event_store
        self._projector = projector
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

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
        """Direct call path — applies the trade AND publishes trades.executed."""
        trade_id = uuid4()
        downstream = await self._apply_trade(
            fund_slug=ctx.fund_slug,
            portfolio_id=portfolio_id,
            instrument_id=instrument_id,
            side=side,
            quantity=quantity,
            price=price,
            currency=currency,
            trade_id=trade_id,
            idempotency_key=idempotency_key,
        )
        if downstream is None:
            return  # idempotent duplicate

        # Publish trades.executed (only from direct path)
        trade_data = {
            "portfolio_id": str(portfolio_id),
            "instrument_id": instrument_id,
            "side": side.value,
            "quantity": str(quantity),
            "price": str(price),
            "trade_id": str(trade_id),
            "currency": currency,
        }
        trade_topic = (
            fund_topic(ctx.fund_slug, "trades.executed") if ctx.fund_slug else "trades.executed"
        )
        await self._event_bus.publish(
            trade_topic,
            BaseEvent(
                event_type=(
                    PositionEventType.TRADE_BUY
                    if side == TradeSide.BUY
                    else PositionEventType.TRADE_SELL
                ),
                data=trade_data,
                actor_id=ctx.actor_id,
                actor_type=ctx.actor_type.value,
                fund_slug=ctx.fund_slug,
            ),
        )

        # Publish downstream (positions.changed, pnl.updated)
        await self._publish_downstream(
            ctx.fund_slug,
            ctx.actor_id,
            ctx.actor_type.value,
            downstream,
        )

        logger.info(
            "trade_processed",
            portfolio_id=str(portfolio_id),
            instrument_id=instrument_id,
            side=side,
            quantity=str(quantity),
            price=str(price),
        )

    async def handle_trade_event(self, event: BaseEvent) -> None:
        """Kafka subscriber path — reacts to trades.executed.

        Applies the trade to the position aggregate and publishes
        downstream events.  Does NOT re-publish trades.executed.
        """
        try:
            data = event.data
            fund_slug = event.fund_slug
            side_str = data["side"]
            side = TradeSide.BUY if side_str == "buy" else TradeSide.SELL
            trade_id = UUID(data["trade_id"]) if "trade_id" in data else uuid4()

            async with self._sf.fund_scope(fund_slug):
                downstream = await self._apply_trade(
                    fund_slug=fund_slug,
                    portfolio_id=UUID(data["portfolio_id"]),
                    instrument_id=data["instrument_id"],
                    side=side,
                    quantity=Decimal(data["quantity"]),
                    price=Decimal(data["price"]),
                    currency=data.get("currency", "USD"),
                    trade_id=trade_id,
                    idempotency_key=str(trade_id),
                )
                if downstream is None:
                    return  # idempotent duplicate

            await self._publish_downstream(
                fund_slug,
                event.actor_id,
                event.actor_type,
                downstream,
            )
        except Exception:
            logger.exception(
                "trade_handler_failed",
                event_id=event.event_id,
            )

    # ------------------------------------------------------------------
    # Core logic (shared by both paths)
    # ------------------------------------------------------------------

    async def _apply_trade(
        self,
        *,
        fund_slug: str | None,
        portfolio_id: UUID,
        instrument_id: str,
        side: TradeSide,
        quantity: Decimal,
        price: Decimal,
        currency: str,
        trade_id: UUID,
        idempotency_key: str | None = None,
    ) -> list[DownstreamEvent] | None:
        """Event-source the trade into the position aggregate.

        Returns downstream events on success, or ``None`` if the trade
        was an idempotent duplicate.
        """
        aggregate_id = f"{portfolio_id}:{instrument_id}"
        now = datetime.now(UTC)
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

        event_metadata: dict[str, str] = {}
        if idempotency_key:
            event_metadata["idempotency_key"] = idempotency_key

        downstream_events: list[DownstreamEvent] = []

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                # fund_scope() or request context ensures the session
                # targets the correct per-fund schema automatically.
                async with self._sf() as session:
                    # Idempotency check
                    if idempotency_key and await self._event_store.has_idempotency_key(
                        idempotency_key,
                        session=session,
                    ):
                        logger.info(
                            "trade_idempotent_duplicate",
                            idempotency_key=idempotency_key,
                        )
                        return None

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

        return downstream_events

    # ------------------------------------------------------------------
    # Event publication helpers
    # ------------------------------------------------------------------

    async def _publish_downstream(
        self,
        fund_slug: str | None,
        actor_id: str | None,
        actor_type: str | None,
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

            topic = fund_topic(fund_slug, base_topic) if fund_slug else base_topic
            data = asdict(de.data)
            serialized_data = {k: str(v) for k, v in data.items()}

            await self._event_bus.publish(
                topic,
                BaseEvent(
                    event_type=de.event_type,
                    data=serialized_data,
                    actor_id=actor_id,
                    actor_type=actor_type,
                    fund_slug=fund_slug,
                ),
            )
