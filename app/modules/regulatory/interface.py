"""Regulatory reporting public interface — DTOs for Form PF, 13F, investor reports."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# 4A. Form PF
# ---------------------------------------------------------------------------


class FormPFFrequency(StrEnum):
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class FormPFSection(StrEnum):
    FUND_INFO = "fund_info"
    LEVERAGE = "leverage"
    COUNTERPARTY = "counterparty"
    LIQUIDITY = "liquidity"
    ASSET_CLASS = "asset_class"
    GEOGRAPHIC = "geographic"
    STRATEGY = "strategy"


class FormPFData(BaseModel):
    """Aggregated data for a Form PF filing."""

    model_config = ConfigDict(frozen=True)

    fund_slug: str
    reporting_period_end: date
    frequency: FormPFFrequency

    # Section 1: Fund Information
    fund_name: str
    gross_asset_value: Decimal
    net_asset_value: Decimal
    total_investors: int
    minimum_investment: Decimal

    # Section 2: Leverage
    gross_notional: Decimal
    net_notional: Decimal
    leverage_ratio_gross: Decimal  # gross_notional / NAV
    leverage_ratio_net: Decimal
    borrowing_total: Decimal

    # Section 3: Counterparty
    top_counterparties: list[dict[str, object]]  # name, exposure, pct_of_nav

    # Section 4: Liquidity
    pct_liquidatable_1_day: Decimal
    pct_liquidatable_7_days: Decimal
    pct_liquidatable_30_days: Decimal
    pct_liquidatable_90_days: Decimal
    pct_illiquid: Decimal
    investor_liquidity: dict[str, object]  # redemption_frequency, notice_period, gate

    # Section 5: Asset class breakdown
    asset_class_breakdown: list[dict[str, object]]  # asset_class, long_value, short_value, pct

    # Section 6: Geographic breakdown
    geographic_breakdown: list[dict[str, object]]  # country, value, pct

    # Section 7: Strategy
    primary_strategy: str
    strategy_description: str

    generated_at: datetime


# ---------------------------------------------------------------------------
# 4B. 13F Filing
# ---------------------------------------------------------------------------


class Filing13FEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    issuer_name: str
    cusip: str | None
    ticker: str
    share_class: str  # "COM", "CL A", etc.
    quantity: Decimal  # shares held
    market_value: Decimal  # in thousands (13F convention)
    investment_discretion: str  # "SOLE", "DEFINED", "OTHER"
    voting_authority_sole: Decimal
    voting_authority_shared: Decimal
    voting_authority_none: Decimal


class Filing13FReport(BaseModel):
    """Complete 13F filing data."""

    model_config = ConfigDict(frozen=True)

    fund_name: str
    cik: str | None  # SEC CIK number
    reporting_period: date  # quarter end
    entries: list[Filing13FEntry]
    total_market_value: Decimal  # in thousands
    total_positions: int
    generated_at: datetime


# ---------------------------------------------------------------------------
# 4C. Investor Reporting
# ---------------------------------------------------------------------------


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
