"""In-process broker adapter — immediate fills with random slippage for dev/test."""

from __future__ import annotations

import random
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from app.shared.adapters.broker import OrderAcknowledgement, OrderStatusReport


class _FillRecord:
    __slots__ = ("client_order_id", "fill_price", "fill_qty")

    def __init__(self, client_order_id: str, fill_price: Decimal, fill_qty: Decimal) -> None:
        self.client_order_id = client_order_id
        self.fill_price = fill_price
        self.fill_qty = fill_qty


class InProcessBrokerAdapter:
    """BrokerAdapter that fills immediately with small random slippage.

    Used when BROKER_ADAPTER=in-process for local dev without mock-exchange.
    """

    def __init__(self) -> None:
        self._fills: dict[str, _FillRecord] = {}

    async def submit_order(
        self,
        client_order_id: str,
        instrument_id: str,
        side: str,
        quantity: Decimal,
        order_type: str,
        limit_price: Decimal | None = None,
    ) -> OrderAcknowledgement:
        base_price = limit_price or Decimal("100.00")
        slippage = Decimal(str(random.uniform(-0.001, 0.001)))
        fill_price = (base_price * (1 + slippage)).quantize(Decimal("0.01"))

        exchange_order_id = str(uuid4())
        self._fills[exchange_order_id] = _FillRecord(client_order_id, fill_price, quantity)
        return OrderAcknowledgement(
            exchange_order_id=exchange_order_id,
            client_order_id=client_order_id,
            status="filled",
            received_at=datetime.now(UTC),
        )

    async def cancel_order(self, exchange_order_id: str) -> bool:
        return False  # In-process broker fills immediately, nothing to cancel

    async def get_order_status(self, exchange_order_id: str) -> OrderStatusReport:
        fill = self._fills.get(exchange_order_id)
        if fill is None:
            return OrderStatusReport(
                exchange_order_id=exchange_order_id,
                client_order_id="",
                status="unknown",
                filled_quantity=Decimal("0"),
                avg_fill_price=None,
            )
        return OrderStatusReport(
            exchange_order_id=exchange_order_id,
            client_order_id=fill.client_order_id,
            status="filled",
            filled_quantity=fill.fill_qty,
            avg_fill_price=fill.fill_price,
        )

    async def get_eod_positions(self, portfolio_id: str, business_date: date) -> dict[str, Decimal]:
        """In-process broker has no persistent state; return empty positions."""
        return {}
