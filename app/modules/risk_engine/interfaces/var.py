"""VaR-related DTOs and enums."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VaRMethod(StrEnum):
    HISTORICAL = "historical"
    PARAMETRIC = "parametric"


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
