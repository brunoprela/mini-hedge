"""Price finalization and snapshot DTOs."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FinalizedPrice(BaseModel):
    model_config = ConfigDict(frozen=True)

    instrument_id: str
    business_date: date
    close_price: Decimal
    source: str
    finalized_at: datetime
    finalized_by: str


class PriceFinalizationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    business_date: date
    total_instruments: int
    finalized_count: int
    missing_count: int
    missing_instruments: list[str]
    is_complete: bool


class NAVSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    business_date: date
    gross_market_value: Decimal
    net_market_value: Decimal
    cash_balance: Decimal
    accrued_fees: Decimal
    nav: Decimal
    nav_per_share: Decimal
    shares_outstanding: Decimal
    currency: str
    computed_at: datetime


class PnLSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    business_date: date
    total_realized_pnl: Decimal
    total_unrealized_pnl: Decimal
    total_pnl: Decimal
    position_count: int
    computed_at: datetime
