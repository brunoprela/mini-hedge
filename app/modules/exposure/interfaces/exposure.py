"""Exposure calculation public interface — Protocol + value objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ExposureDimension(StrEnum):
    INSTRUMENT = "instrument"
    SECTOR = "sector"
    COUNTRY = "country"
    CURRENCY = "currency"
    ASSET_CLASS = "asset_class"


class ExposureSide(StrEnum):
    LONG = "long"
    SHORT = "short"


# ---------------------------------------------------------------------------
# Internal value objects (frozen dataclasses)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PositionValue:
    """A position with its current market value for exposure calc."""

    instrument_id: str
    quantity: Decimal
    market_price: Decimal
    market_value: Decimal
    asset_class: str | None = None
    sector: str | None = None
    country: str | None = None
    currency: str = "USD"


@dataclass(frozen=True)
class ExposureBreakdown:
    """Exposure breakdown by a single dimension key."""

    dimension: ExposureDimension
    key: str
    long_value: Decimal
    short_value: Decimal
    net_value: Decimal
    gross_value: Decimal
    weight_pct: Decimal


# ---------------------------------------------------------------------------
# API / read-model value objects (Pydantic — serialization boundary)
# ---------------------------------------------------------------------------


class PortfolioExposure(BaseModel):
    """Exposure summary for a portfolio."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    gross_exposure: Decimal
    net_exposure: Decimal
    long_exposure: Decimal
    short_exposure: Decimal
    long_count: int
    short_count: int
    calculated_at: datetime
    breakdowns: dict[str, list[ExposureBreakdown]] = {}


class ExposureSnapshot(BaseModel):
    """Persisted exposure snapshot."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    portfolio_id: UUID
    fund_slug: str
    gross_exposure: Decimal
    net_exposure: Decimal
    long_exposure: Decimal
    short_exposure: Decimal
    long_count: int
    short_count: int
    snapshot_at: datetime


# ---------------------------------------------------------------------------
# Module protocol — the public read interface for other modules
# ---------------------------------------------------------------------------


class ExposureReader(Protocol):
    """Public read interface for other modules."""

    async def get_current(self, portfolio_id: UUID) -> PortfolioExposure | None: ...

    async def get_history(
        self,
        portfolio_id: UUID,
        start: datetime,
        end: datetime,
    ) -> list[ExposureSnapshot]: ...
