"""Backtesting module public interface — enums and DTOs."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class BacktestStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RebalanceFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class BenchmarkType(StrEnum):
    INDEX = "index"
    PORTFOLIO = "portfolio"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


class BacktestConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy_name: str
    start_date: date
    end_date: date
    initial_capital: Decimal
    rebalance_frequency: RebalanceFrequency
    benchmark: str | None = None
    slippage_bps: int = 5
    commission_bps: int = 10
    universe: list[str]  # instrument_ids


class EquityCurvePoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    date: date
    portfolio_value: Decimal
    benchmark_value: Decimal | None = None
    drawdown: Decimal


class MonthlyReturn(BaseModel):
    model_config = ConfigDict(frozen=True)

    year: int
    month: int
    return_pct: Decimal
    benchmark_return_pct: Decimal | None = None


class BacktestTrade(BaseModel):
    model_config = ConfigDict(frozen=True)

    date: date
    instrument_id: str
    side: str  # "buy" or "sell"
    quantity: Decimal
    price: Decimal
    commission: Decimal
    slippage: Decimal


class BacktestResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    config: BacktestConfig
    status: BacktestStatus
    total_return: Decimal
    annualized_return: Decimal
    sharpe_ratio: Decimal
    max_drawdown: Decimal
    volatility: Decimal
    calmar_ratio: Decimal
    sortino_ratio: Decimal
    win_rate: Decimal
    profit_factor: Decimal
    total_trades: int
    avg_holding_period_days: Decimal
    equity_curve: list[EquityCurvePoint]
    trades: list[BacktestTrade]
    monthly_returns: list[MonthlyReturn]
    created_at: datetime
    completed_at: datetime | None = None


class BacktestSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    strategy_name: str
    status: BacktestStatus
    total_return: Decimal
    sharpe_ratio: Decimal
    max_drawdown: Decimal
    created_at: datetime
