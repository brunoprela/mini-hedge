"""In-process broker adapter — wraps existing MockBrokerAdapter for backward compat."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.modules.orders.mock_broker import MockBrokerAdapter
from app.shared.adapters import OrderAcknowledgement, OrderStatusReport


class _FillRecord:
    __slots__ = ("client_order_id", "fill_price", "fill_qty")

    def __init__(self, client_order_id: str, fill_price: Decimal, fill_qty: Decimal) -> None:
        self.client_order_id = client_order_id
        self.fill_price = fill_price
        self.fill_qty = fill_qty


class InProcessBrokerAdapter:
    """BrokerAdapter that delegates to the existing MockBrokerAdapter.

    Used when BROKER_ADAPTER=in-process to preserve the current
    synchronous-fill behavior without requiring mock-exchange.
    """

    def __init__(self) -> None:
        self._broker = MockBrokerAdapter()
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
        fill_price, fill_qty = await self._broker.submit_order(
            instrument_id=instrument_id,
            side=side,
            quantity=quantity,
            price=limit_price,
        )
        exchange_order_id = str(uuid4())
        self._fills[exchange_order_id] = _FillRecord(client_order_id, fill_price, fill_qty)
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
