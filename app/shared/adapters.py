"""Adapter protocols for external data sources.

These define the contracts that all adapters must implement — mock-exchange,
Bloomberg, LSEG, FIX brokers, DTCC, etc. Modules depend ONLY on these
protocols, never on concrete adapter implementations.

Swapping mock-exchange for a production vendor means:
1. Write a new adapter implementing the relevant Protocol
2. Register it in adapter_factory.py
3. Set the env var (e.g., BROKER_ADAPTER=bloomberg)
4. Zero changes to any module code
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import date, datetime
    from decimal import Decimal



# ---------------------------------------------------------------------------
#  Value objects returned by adapters (vendor-agnostic)
# ---------------------------------------------------------------------------


class ExternalInstrument:
    """Instrument reference data from an external source."""

    __slots__ = (
        "ticker",
        "name",
        "asset_class",
        "currency",
        "exchange",
        "country",
        "sector",
        "industry",
        "annual_drift",
        "annual_volatility",
        "spread_bps",
        "is_active",
    )

    def __init__(
        self,
        *,
        ticker: str,
        name: str,
        asset_class: str,
        currency: str,
        exchange: str,
        country: str,
        sector: str,
        industry: str,
        annual_drift: float = 0.08,
        annual_volatility: float = 0.25,
        spread_bps: float = 10.0,
        is_active: bool = True,
    ) -> None:
        self.ticker = ticker
        self.name = name
        self.asset_class = asset_class
        self.currency = currency
        self.exchange = exchange
        self.country = country
        self.sector = sector
        self.industry = industry
        self.annual_drift = annual_drift
        self.annual_volatility = annual_volatility
        self.spread_bps = spread_bps
        self.is_active = is_active


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


class CorporateAction:
    """Corporate action event from an external source."""

    __slots__ = (
        "action_id",
        "instrument_id",
        "action_type",
        "ex_date",
        "record_date",
        "pay_date",
        "amount",
        "currency",
    )

    def __init__(
        self,
        *,
        action_id: str,
        instrument_id: str,
        action_type: str,
        ex_date: date,
        record_date: date | None = None,
        pay_date: date | None = None,
        amount: Decimal | None = None,
        currency: str = "USD",
    ) -> None:
        self.action_id = action_id
        self.instrument_id = instrument_id
        self.action_type = action_type
        self.ex_date = ex_date
        self.record_date = record_date
        self.pay_date = pay_date
        self.amount = amount
        self.currency = currency


# ---------------------------------------------------------------------------
#  Adapter protocols
# ---------------------------------------------------------------------------


class MarketDataAdapter(Protocol):
    """Vendor-agnostic market data source.

    Implementations: mock-exchange, Bloomberg BLPAPI HTTP, LSEG RDP, Massive.
    """

    async def start_streaming(self, instruments: list[str]) -> None:
        """Begin pushing prices to the platform (e.g. via Kafka)."""
        ...

    async def stop_streaming(self) -> None: ...


class ReferenceDataAdapter(Protocol):
    """Vendor-agnostic reference data source.

    Implementations: mock-exchange, DTCC, Bloomberg FIGI.
    """

    async def get_instrument(self, ticker: str) -> ExternalInstrument | None: ...

    async def get_all_instruments(
        self, asset_class: str | None = None
    ) -> list[ExternalInstrument]: ...


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


class CorporateActionsAdapter(Protocol):
    """Vendor-agnostic corporate actions source.

    Implementations: mock-exchange, LSEG RDP.
    """

    async def get_actions(
        self,
        instrument_id: str | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> list[CorporateAction]: ...
