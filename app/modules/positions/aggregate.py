"""Event-sourced position aggregate — pure domain logic, no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid5

from app.modules.positions.interface import (
    DownstreamEvent,
    PnLRealized,
    PnLRealizedData,
    PositionChanged,
    PositionChangedData,
    PositionEventType,
    TradeEvent,
)


@dataclass
class LotState:
    lot_id: UUID
    quantity: Decimal
    original_quantity: Decimal
    price: Decimal
    acquired_at: datetime
    trade_id: UUID


@dataclass
class PositionAggregate:
    """Event-sourced position aggregate. State is derived entirely from events.

    This class has NO I/O dependencies — it is pure logic and fully unit-testable.
    """

    portfolio_id: UUID
    instrument_id: str
    quantity: Decimal = Decimal(0)
    cost_basis: Decimal = Decimal(0)
    realized_pnl: Decimal = Decimal(0)
    currency: str = "USD"
    lots: list[LotState] = field(default_factory=list)
    version: int = 0

    @property
    def avg_cost(self) -> Decimal:
        if self.quantity == 0:
            return Decimal(0)
        return self.cost_basis / abs(self.quantity)

    def apply(self, event: TradeEvent) -> list[DownstreamEvent]:
        """Apply an event and return any downstream events to emit."""
        match event.event_type:
            case PositionEventType.TRADE_BUY:
                return self._apply_buy(event)
            case PositionEventType.TRADE_SELL:
                return self._apply_sell(event)
            case _:
                return []

    def _apply_buy(self, event: TradeEvent) -> list[DownstreamEvent]:
        qty = event.data.quantity
        price = event.data.price
        trade_id = event.data.trade_id
        self.currency = event.data.currency

        self.quantity += qty
        self.cost_basis += qty * price

        self.lots.append(
            LotState(
                lot_id=uuid5(trade_id, "lot"),
                quantity=qty,
                original_quantity=qty,
                price=price,
                acquired_at=event.timestamp,
                trade_id=trade_id,
            )
        )

        self.version += 1
        return [self._position_changed_event()]

    def _apply_sell(self, event: TradeEvent) -> list[DownstreamEvent]:
        qty = event.data.quantity
        price = event.data.price
        trade_id = event.data.trade_id
        self.currency = event.data.currency

        # FIFO lot matching
        remaining = qty
        realized = Decimal(0)

        for lot in sorted(self.lots, key=lambda x: (x.acquired_at, x.lot_id)):
            if remaining <= 0 or lot.quantity <= 0:
                break
            sold_from_lot = min(remaining, lot.quantity)
            realized += sold_from_lot * (price - lot.price)
            lot.quantity -= sold_from_lot
            remaining -= sold_from_lot

        # Remove exhausted lots
        self.lots = [lot for lot in self.lots if lot.quantity > 0]

        # Short selling: remaining quantity opens a short lot
        if remaining > 0:
            self.lots.append(
                LotState(
                    lot_id=uuid5(trade_id, "short"),
                    quantity=-remaining,
                    original_quantity=-remaining,
                    price=price,
                    acquired_at=event.timestamp,
                    trade_id=trade_id,
                )
            )

        self.quantity -= qty
        self.cost_basis = sum(abs(lot.quantity) * lot.price for lot in self.lots)
        self.realized_pnl += realized

        self.version += 1
        return [
            self._position_changed_event(),
            self._pnl_realized_event(realized, price),
        ]

    def _position_changed_event(self) -> PositionChanged:
        return PositionChanged(
            event_type=PositionEventType.POSITION_CHANGED,
            data=PositionChangedData(
                portfolio_id=self.portfolio_id,
                instrument_id=self.instrument_id,
                quantity=self.quantity,
                avg_cost=self.avg_cost,
                cost_basis=self.cost_basis,
                currency=self.currency,
            ),
        )

    def _pnl_realized_event(self, amount: Decimal, price: Decimal) -> PnLRealized:
        return PnLRealized(
            event_type=PositionEventType.PNL_REALIZED,
            data=PnLRealizedData(
                portfolio_id=self.portfolio_id,
                instrument_id=self.instrument_id,
                realized_pnl=amount,
                price=price,
                currency=self.currency,
            ),
        )

    @classmethod
    def from_events(
        cls,
        portfolio_id: UUID,
        instrument_id: str,
        events: list[TradeEvent],
    ) -> PositionAggregate:
        aggregate = cls(portfolio_id=portfolio_id, instrument_id=instrument_id)
        for event in events:
            if event.data.portfolio_id != portfolio_id or event.data.instrument_id != instrument_id:
                raise ValueError(
                    f"Event {event.event_type} belongs to "
                    f"{event.data.portfolio_id}:{event.data.instrument_id}, "
                    f"expected {portfolio_id}:{instrument_id}"
                )
            aggregate.apply(event)
        return aggregate
