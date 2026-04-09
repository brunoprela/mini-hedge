"""Investor reporting DTOs."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class InvestorStatement(BaseModel):
    """Quarterly capital account statement for an investor."""

    model_config = ConfigDict(frozen=True)

    investor_id: UUID
    investor_name: str
    share_class: str
    period_start: date
    period_end: date

    beginning_capital: Decimal
    contributions: Decimal
    withdrawals: Decimal
    gross_return: Decimal
    management_fees: Decimal
    performance_fees: Decimal
    net_return: Decimal
    ending_capital: Decimal

    ownership_pct: Decimal
    shares_held: Decimal
    nav_per_share: Decimal

    gross_return_pct: Decimal
    net_return_pct: Decimal
    ytd_return_pct: Decimal
    itd_return_pct: Decimal  # inception-to-date

    generated_at: datetime


class MonthlyPerformanceLetter(BaseModel):
    """Monthly fund performance summary."""

    model_config = ConfigDict(frozen=True)

    fund_name: str
    fund_slug: str
    period: date  # month end

    gross_return_pct: Decimal
    net_return_pct: Decimal
    benchmark_return_pct: Decimal
    active_return_pct: Decimal

    ytd_gross_pct: Decimal
    ytd_net_pct: Decimal
    itd_annualized_pct: Decimal

    total_aum: Decimal
    total_investors: int
    nav_per_share: Decimal

    top_contributors: list[dict[str, object]]  # instrument_id, contribution_pct
    top_detractors: list[dict[str, object]]

    sector_attribution: list[dict[str, object]]  # sector, allocation, selection
    risk_metrics: dict[str, object]  # var_95, sharpe, max_drawdown

    generated_at: datetime
