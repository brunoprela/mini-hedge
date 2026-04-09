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


class PriceWriter(Protocol):
    """Write interface for price ingestion (simulator, feeds)."""

    def update_latest(self, snapshot: PriceSnapshot) -> None: ...

    async def store_price(self, snapshot: PriceSnapshot) -> None: ...
