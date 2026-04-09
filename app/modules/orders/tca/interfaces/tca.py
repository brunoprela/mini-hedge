"""TCA public interface — response models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TCAReport(BaseModel):
    """TCA result for a single order."""

    model_config = ConfigDict(frozen=True)

    order_id: UUID
    instrument_id: str
    side: str
    quantity: Decimal
    filled_quantity: Decimal
    avg_fill_price: Decimal | None

    # Benchmarks
    arrival_mid_price: Decimal
    arrival_spread: Decimal
    vwap_benchmark: Decimal | None

    # Cost decomposition (basis points)
    total_cost_bps: Decimal
    commission_cost_bps: Decimal
    spread_cost_bps: Decimal
    market_impact_cost_bps: Decimal
    timing_cost_bps: Decimal
    opportunity_cost_bps: Decimal
    implementation_shortfall_bps: Decimal

    # Participation
    participation_rate: Decimal | None
    execution_duration_seconds: int

    # Dollar amounts
    total_cost_usd: Decimal

    computed_at: datetime


class PortfolioTCAReport(BaseModel):
    """Aggregated TCA for all orders in a portfolio."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    total_orders: int
    avg_total_cost_bps: Decimal
    avg_commission_bps: Decimal
    avg_spread_bps: Decimal
    avg_impact_bps: Decimal
    avg_timing_bps: Decimal
    total_cost_usd: Decimal
    orders: list[TCAReport]


class FundTCASummary(BaseModel):
    """High-level TCA summary for a fund."""

    model_config = ConfigDict(frozen=True)

    fund_slug: str
    period_start: datetime
    period_end: datetime
    total_orders_analyzed: int
    avg_implementation_shortfall_bps: Decimal
    avg_commission_bps: Decimal
    avg_spread_bps: Decimal
    avg_impact_bps: Decimal
    total_cost_usd: Decimal
