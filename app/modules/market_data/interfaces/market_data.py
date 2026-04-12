"""Market data public interface — Protocol + value objects.

Other modules depend ONLY on this file, never on internals.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class PriceSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    instrument_id: str
    bid: Decimal
    ask: Decimal
    mid: Decimal
    volume: Decimal | None = None
    timestamp: datetime
    source: str


class MarketDataReader(Protocol):
    """Read interface exposed to other modules."""

    async def get_latest_price(self, instrument_id: str) -> PriceSnapshot | None: ...

    async def get_price_history(
        self,
        instrument_id: str,
        start: datetime,
        end: datetime,
    ) -> list[PriceSnapshot]: ...


class FXRateSnapshot(BaseModel):
    """Immutable snapshot of a single FX rate."""

    model_config = ConfigDict(frozen=True)

    base_currency: str  # e.g. "USD"
    quote_currency: str  # e.g. "GBP"
    rate: Decimal  # 1 base = rate quote
    timestamp: datetime
    source: str


# ---------------------------------------------------------------------------
# Asset-class-specific price DTOs
# ---------------------------------------------------------------------------


class OHLCVBar(BaseModel):
    """Open-High-Low-Close-Volume bar for a single period."""

    model_config = ConfigDict(frozen=True)

    instrument_id: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    period_start: datetime
    period_end: datetime
    source: str


class FixedIncomePriceSnapshot(BaseModel):
    """Price snapshot for fixed income instruments."""

    model_config = ConfigDict(frozen=True)

    instrument_id: str
    clean_price: Decimal
    dirty_price: Decimal
    accrued_interest: Decimal
    yield_to_maturity: Decimal | None = None
    spread_to_benchmark: Decimal | None = None
    benchmark_id: str | None = None
    timestamp: datetime
    source: str


class OptionPriceSnapshot(BaseModel):
    """Price snapshot for options with greeks."""

    model_config = ConfigDict(frozen=True)

    instrument_id: str
    bid: Decimal
    ask: Decimal
    mid: Decimal
    underlying_price: Decimal
    implied_volatility: Decimal | None = None
    delta: Decimal | None = None
    gamma: Decimal | None = None
    theta: Decimal | None = None
    vega: Decimal | None = None
    rho: Decimal | None = None
    timestamp: datetime
    source: str


class FuturePriceSnapshot(BaseModel):
    """Price snapshot for futures contracts."""

    model_config = ConfigDict(frozen=True)

    instrument_id: str
    bid: Decimal
    ask: Decimal
    mid: Decimal
    settlement_price: Decimal | None = None
    open_interest: Decimal | None = None
    volume: Decimal | None = None
    basis: Decimal | None = None
    timestamp: datetime
    source: str


class FXForwardSnapshot(BaseModel):
    """Price snapshot for FX forwards."""

    model_config = ConfigDict(frozen=True)

    base_currency: str
    quote_currency: str
    spot_rate: Decimal
    forward_rate: Decimal
    forward_points: Decimal
    tenor: str  # e.g. "1M", "3M", "1Y"
    timestamp: datetime
    source: str


class PriceWriter(Protocol):
    """Write interface for price ingestion (simulator, feeds)."""

    def update_latest(self, snapshot: PriceSnapshot) -> None: ...

    async def store_price(self, snapshot: PriceSnapshot) -> None: ...
