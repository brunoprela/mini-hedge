"""ReferenceDataAdapter protocol and ExternalInstrument value object."""

from __future__ import annotations

from typing import Protocol


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
        "avg_daily_volume",
        "market_cap_usd",
        "lot_size",
        "tick_size",
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
        avg_daily_volume: int = 0,
        market_cap_usd: float = 0.0,
        lot_size: int = 1,
        tick_size: float = 0.01,
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
        self.avg_daily_volume = avg_daily_volume
        self.market_cap_usd = market_cap_usd
        self.lot_size = lot_size
        self.tick_size = tick_size


class ReferenceDataAdapter(Protocol):
    """Vendor-agnostic reference data source.

    Implementations: mock-exchange, DTCC, Bloomberg FIGI.
    """

    async def get_instrument(self, ticker: str) -> ExternalInstrument | None: ...

    async def get_all_instruments(
        self, asset_class: str | None = None
    ) -> list[ExternalInstrument]: ...
