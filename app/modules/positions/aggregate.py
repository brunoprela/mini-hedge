"""Event-sourced position aggregate — pure domain logic, no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4


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
    lots: list[LotState] = field(default_factory=list)
    version: int = 0

    @property
    def avg_cost(self) -> Decimal:
        if self.quantity == 0:
            return Decimal(0)
        return self.cost_basis / self.quantity

    def apply(self, event: dict) -> list[dict]:
        """Apply an event and return any downstream events to emit."""
        match event["event_type"]:
            case "trade.buy":
                return self._apply_buy(event)
            case "trade.sell":
                return self._apply_sell(event)
            case _:
                return []

    def _apply_buy(self, event: dict) -> list[dict]:
        qty = Decimal(str(event["data"]["quantity"]))
        price = Decimal(str(event["data"]["price"]))
        trade_id = UUID(event["data"]["trade_id"])

        self.quantity += qty
        self.cost_basis += qty * price

        self.lots.append(
            LotState(
                lot_id=uuid4(),
                quantity=qty,
                original_quantity=qty,
                price=price,
                acquired_at=datetime.fromisoformat(event["timestamp"]),
                trade_id=trade_id,
            )
        )

        self.version += 1
        return [self._position_changed_event()]

    def _apply_sell(self, event: dict) -> list[dict]:
        qty = Decimal(str(event["data"]["quantity"]))
        price = Decimal(str(event["data"]["price"]))
        trade_id = UUID(event["data"]["trade_id"])

        # FIFO lot matching
        remaining = qty
        realized = Decimal(0)

        for lot in sorted(self.lots, key=lambda x: x.acquired_at):
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
                    lot_id=uuid4(),
                    quantity=-remaining,
                    original_quantity=-remaining,
                    price=price,
                    acquired_at=datetime.fromisoformat(event["timestamp"]),
                    trade_id=trade_id,
                )
            )

        self.quantity -= qty
        self.cost_basis = sum(lot.quantity * lot.price for lot in self.lots)
        self.realized_pnl += realized

        self.version += 1
        return [
            self._position_changed_event(),
            self._pnl_realized_event(realized, price),
        ]

    def _position_changed_event(self) -> dict:
        return {
            "event_type": "position.changed",
            "data": {
                "portfolio_id": str(self.portfolio_id),
                "instrument_id": self.instrument_id,
                "quantity": str(self.quantity),
                "avg_cost": str(self.avg_cost),
                "cost_basis": str(self.cost_basis),
            },
        }

    def _pnl_realized_event(self, amount: Decimal, price: Decimal) -> dict:
        return {
            "event_type": "pnl.realized",
            "data": {
                "portfolio_id": str(self.portfolio_id),
                "instrument_id": self.instrument_id,
                "realized_amount": str(amount),
                "price": str(price),
            },
        }

    @classmethod
    def from_events(
        cls,
        portfolio_id: UUID,
        instrument_id: str,
        events: list[dict],
    ) -> PositionAggregate:
        aggregate = cls(portfolio_id=portfolio_id, instrument_id=instrument_id)
        for event in events:
            aggregate.apply(event)
        return aggregate
