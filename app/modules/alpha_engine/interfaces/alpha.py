"""Alpha engine public interface — Protocol + value objects."""

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


class OptimizationObjective(StrEnum):
    MIN_VARIANCE = "min_variance"
    MAX_SHARPE = "max_sharpe"
    RISK_PARITY = "risk_parity"


class ScenarioStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class OrderIntentStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Internal value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HypotheticalTrade:
    """A single hypothetical trade for what-if analysis."""

    instrument_id: str
    side: str  # "buy" or "sell"
    quantity: Decimal
    price: Decimal


@dataclass(frozen=True)
class WhatIfPosition:
    """Position state after applying hypothetical trades."""

    instrument_id: str
    current_quantity: Decimal
    proposed_quantity: Decimal
    current_value: Decimal
    proposed_value: Decimal
    current_weight: Decimal
    proposed_weight: Decimal


@dataclass(frozen=True)
class OptimizationWeight:
    """Target weight from portfolio optimization."""

    instrument_id: str
    current_weight: Decimal
    target_weight: Decimal
    delta_weight: Decimal
    delta_shares: Decimal
    delta_value: Decimal


@dataclass(frozen=True)
class OrderIntent:
    """Generated order intent from optimization."""

    instrument_id: str
    side: str
    quantity: Decimal
    estimated_value: Decimal
    reason: str


# ---------------------------------------------------------------------------
# API / read-model value objects (Pydantic)
# ---------------------------------------------------------------------------


class WhatIfResult(BaseModel):
    """Result of a what-if scenario analysis."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    scenario_name: str
    current_nav: Decimal
    proposed_nav: Decimal
    nav_change: Decimal
    nav_change_pct: Decimal
    current_var_95: Decimal | None = None
    proposed_var_95: Decimal | None = None
    positions: list[WhatIfPosition] = []
    compliance_issues: list[str] = []
    calculated_at: datetime


class OptimizationResult(BaseModel):
    """Result of a portfolio optimization run."""

    model_config = ConfigDict(frozen=True)

    id: UUID | None = None
    portfolio_id: UUID
    objective: OptimizationObjective
    expected_return: Decimal
    expected_risk: Decimal
    sharpe_ratio: Decimal | None = None
    weights: list[OptimizationWeight] = []
    order_intents: list[OrderIntent] = []
    calculated_at: datetime


class ScenarioRun(BaseModel):
    """Persisted what-if scenario run."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    portfolio_id: UUID
    scenario_name: str
    trades: list[dict[str, str]]
    result_summary: dict[str, str]
    status: ScenarioStatus
    created_at: datetime


# ---------------------------------------------------------------------------
# Module protocol
# ---------------------------------------------------------------------------


class AlphaReader(Protocol):
    """Public read interface for other modules."""

    async def run_what_if(
        self,
        portfolio_id: UUID,
        scenario_name: str,
        trades: list[HypotheticalTrade],
    ) -> WhatIfResult: ...

    async def optimize(
        self,
        portfolio_id: UUID,
        objective: OptimizationObjective,
    ) -> OptimizationResult: ...
