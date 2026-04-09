"""Liquidity risk DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LiquidityProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    business_date: datetime
    total_nav: Decimal
    pct_1_day: Decimal
    pct_1_week: Decimal
    pct_1_month: Decimal
    pct_3_months: Decimal
    pct_illiquid: Decimal
    weighted_days_to_liquidate: Decimal
    redemption_coverage_pct: Decimal
    position_details: list[dict] = []


@dataclass(frozen=True)
class PositionLiquidity:
    instrument_id: str
    market_value: Decimal
    avg_daily_volume_usd: Decimal
    days_to_liquidate: Decimal
    liquidity_bucket: str  # "1d", "1w", "1m", "3m", "illiquid"
    pct_of_nav: Decimal
