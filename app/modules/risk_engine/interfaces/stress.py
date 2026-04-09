"""Stress testing DTOs and enums."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class StressScenarioType(StrEnum):
    PREDEFINED = "predefined"
    CUSTOM = "custom"


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
