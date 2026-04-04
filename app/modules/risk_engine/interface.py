"""Risk engine public interface — Protocol + value objects."""

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


class VaRMethod(StrEnum):
    HISTORICAL = "historical"
    PARAMETRIC = "parametric"


class StressScenarioType(StrEnum):
    PREDEFINED = "predefined"
    CUSTOM = "custom"


class RiskFactor(StrEnum):
    MARKET = "market"
    SECTOR = "sector"
    IDIOSYNCRATIC = "idiosyncratic"


# ---------------------------------------------------------------------------
# Internal value objects (frozen dataclasses)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PortfolioReturn:
    """Single-period portfolio return for historical VaR."""

    date: datetime
    portfolio_return: float
    position_returns: dict[str, float]  # instrument_id -> return


@dataclass(frozen=True)
class VaRContribution:
    """Instrument-level contribution to portfolio VaR."""

    instrument_id: str
    weight: Decimal
    marginal_var: Decimal
    component_var: Decimal
    pct_contribution: Decimal


@dataclass(frozen=True)
class StressScenario:
    """Defines a stress test scenario."""

    name: str
    scenario_type: StressScenarioType
    shocks: dict[str, float]  # instrument_id or factor -> shock magnitude
    description: str = ""


@dataclass(frozen=True)
class StressPositionImpact:
    """Per-position impact from a stress scenario."""

    instrument_id: str
    current_value: Decimal
    stressed_value: Decimal
    pnl_impact: Decimal
    pct_change: Decimal


@dataclass(frozen=True)
class FactorExposure:
    """Exposure to a single risk factor."""

    factor: RiskFactor
    factor_name: str
    beta: Decimal
    exposure_value: Decimal
    pct_of_total: Decimal


# ---------------------------------------------------------------------------
# API / read-model value objects (Pydantic)
# ---------------------------------------------------------------------------


class VaRResult(BaseModel):
    """Value at Risk calculation result."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    method: VaRMethod
    confidence_level: float
    horizon_days: int
    var_amount: Decimal
    var_pct: Decimal
    expected_shortfall: Decimal
    contributions: list[VaRContribution] = []
    calculated_at: datetime


class StressTestResult(BaseModel):
    """Result of a stress test scenario."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    scenario_name: str
    scenario_type: StressScenarioType
    total_pnl_impact: Decimal
    total_pct_change: Decimal
    position_impacts: list[StressPositionImpact] = []
    calculated_at: datetime


class FactorDecomposition(BaseModel):
    """Factor model decomposition of portfolio risk."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    total_risk: Decimal
    systematic_risk: Decimal
    idiosyncratic_risk: Decimal
    systematic_pct: Decimal
    factor_exposures: list[FactorExposure] = []
    calculated_at: datetime


class RiskSnapshot(BaseModel):
    """Complete risk snapshot for a portfolio."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    portfolio_id: UUID
    nav: Decimal
    var_95_1d: Decimal
    var_99_1d: Decimal
    expected_shortfall_95: Decimal
    max_drawdown: Decimal
    sharpe_ratio: Decimal | None = None
    snapshot_at: datetime


# ---------------------------------------------------------------------------
# Predefined stress scenarios
# ---------------------------------------------------------------------------


PREDEFINED_SCENARIOS: list[StressScenario] = [
    StressScenario(
        name="Market Crash -20%",
        scenario_type=StressScenarioType.PREDEFINED,
        shocks={"market": -0.20},
        description="Broad market decline of 20%",
    ),
    StressScenario(
        name="Tech Selloff -30%",
        scenario_type=StressScenarioType.PREDEFINED,
        shocks={"Technology": -0.30, "market": -0.10},
        description="Tech sector drops 30%, broader market drops 10%",
    ),
    StressScenario(
        name="Rate Shock +200bps",
        scenario_type=StressScenarioType.PREDEFINED,
        shocks={"Financials": 0.05, "Technology": -0.15, "market": -0.08},
        description="Interest rate shock: financials benefit, growth sells off",
    ),
    StressScenario(
        name="Energy Crisis",
        scenario_type=StressScenarioType.PREDEFINED,
        shocks={"Energy": 0.25, "market": -0.12, "Consumer Discretionary": -0.18},
        description="Energy spike: energy stocks up, consumer/market down",
    ),
    StressScenario(
        name="EM Contagion",
        scenario_type=StressScenarioType.PREDEFINED,
        shocks={"market": -0.15, "Financials": -0.20},
        description="Emerging market contagion hitting global financials",
    ),
]


# ---------------------------------------------------------------------------
# Module protocol
# ---------------------------------------------------------------------------


class RiskReader(Protocol):
    """Public read interface for other modules."""

    async def get_latest_snapshot(self, portfolio_id: UUID) -> RiskSnapshot | None: ...

    async def calculate_var(
        self,
        portfolio_id: UUID,
        method: VaRMethod,
        confidence: float,
        horizon_days: int,
    ) -> VaRResult: ...

    async def run_stress_test(
        self,
        portfolio_id: UUID,
        scenario: StressScenario,
    ) -> StressTestResult: ...
