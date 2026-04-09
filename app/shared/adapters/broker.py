"""BrokerAdapter protocol and order value objects."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import date, datetime
    from decimal import Decimal


class OrderAcknowledgement:
    """Broker acknowledgement after order submission."""

    __slots__ = ("exchange_order_id", "client_order_id", "status", "received_at")

    def __init__(
        self,
        *,
        exchange_order_id: str,
        client_order_id: str,
        status: str,
        received_at: datetime,
    ) -> None:
        self.exchange_order_id = exchange_order_id
        self.client_order_id = client_order_id
        self.status = status
        self.received_at = received_at


class OrderStatusReport:
    """Full order status including fills."""

    __slots__ = (
        "exchange_order_id",
        "client_order_id",
        "status",
        "filled_quantity",
        "avg_fill_price",
    )

    def __init__(
        self,
        *,
        exchange_order_id: str,
        client_order_id: str,
        status: str,
        filled_quantity: Decimal,
        avg_fill_price: Decimal | None,
    ) -> None:
        self.exchange_order_id = exchange_order_id
        self.client_order_id = client_order_id
        self.status = status
        self.filled_quantity = filled_quantity
        self.avg_fill_price = avg_fill_price


class BrokerAdapter(Protocol):
    """Vendor-agnostic order execution.

    Implementations: mock-exchange REST, FIX 4.4, IB TWS.
    """

    async def submit_order(
        self,
        client_order_id: str,
        instrument_id: str,
        side: str,
        quantity: Decimal,
        order_type: str,
        limit_price: Decimal | None = None,
    ) -> OrderAcknowledgement: ...

    async def cancel_order(self, exchange_order_id: str) -> bool: ...

    async def get_order_status(self, exchange_order_id: str) -> OrderStatusReport: ...

    async def get_eod_positions(self, portfolio_id: str, business_date: date) -> dict[str, Decimal]:
        """Return instrument_id -> quantity from the broker's EOD statement.

        Used by the position reconciler to compare against internal positions.
        """
        ...
