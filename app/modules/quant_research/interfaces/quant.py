"""Quant research public interface — enums and DTOs."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FactorType(StrEnum):
    VALUE = "value"
    MOMENTUM = "momentum"
    SIZE = "size"
    QUALITY = "quality"
    VOLATILITY = "volatility"
    GROWTH = "growth"
    LIQUIDITY = "liquidity"
    CUSTOM = "custom"


class RegimeType(StrEnum):
    BULL = "bull"
    BEAR = "bear"
    HIGH_VOL = "high_vol"
    LOW_VOL = "low_vol"
    CRISIS = "crisis"
    RECOVERY = "recovery"
    NORMAL = "normal"


class RegimeDetectionMethod(StrEnum):
    HMM = "hmm"
    ROLLING_STATS = "rolling_stats"
    THRESHOLD = "threshold"


# ---------------------------------------------------------------------------
# Factor Research DTOs
# ---------------------------------------------------------------------------


class FactorDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    factor_type: FactorType
    description: str
    formula: str
    parameters: dict
    is_active: bool


class FactorExposure(BaseModel):
    model_config = ConfigDict(frozen=True)

    factor_name: str
    instrument_id: str
    exposure: Decimal
    z_score: Decimal
    as_of_date: date


class FactorReturn(BaseModel):
    model_config = ConfigDict(frozen=True)

    factor_name: str
    date: date
    return_pct: Decimal
    cumulative_return: Decimal


class FactorAnalysisResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    factor_name: str
    start_date: date
    end_date: date
    mean_return: Decimal
    volatility: Decimal
    sharpe_ratio: Decimal
    max_drawdown: Decimal
    correlation_matrix: dict[str, dict[str, float]]
    top_exposures: list[FactorExposure]


class PortfolioFactorDecomposition(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    as_of_date: date
    factors: list[FactorExposure]
    explained_variance_pct: Decimal
    residual_pct: Decimal


# ---------------------------------------------------------------------------
# Regime Detection DTOs
# ---------------------------------------------------------------------------


class MarketRegime(BaseModel):
    model_config = ConfigDict(frozen=True)

    regime_type: RegimeType
    start_date: date
    end_date: date | None
    confidence: Decimal
    indicators: dict[str, Decimal]


class RegimeIndicator(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    value: Decimal
    threshold_low: Decimal
    threshold_high: Decimal
    signal: str  # "bullish" / "bearish" / "neutral"


class RegimeAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)

    current_regime: RegimeType
    confidence: Decimal
    regime_history: list[MarketRegime]
    indicators: list[RegimeIndicator]
    transition_probabilities: dict[str, dict[str, float]]


class RegimeConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    method: RegimeDetectionMethod = RegimeDetectionMethod.ROLLING_STATS
    lookback_days: int = 252
    vol_window: int = 21
    trend_window: int = 63
    vol_threshold_high: Decimal = Decimal("0.25")
    vol_threshold_low: Decimal = Decimal("0.12")
