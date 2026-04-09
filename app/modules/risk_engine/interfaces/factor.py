"""Factor decomposition DTOs and enums."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RiskFactor(StrEnum):
    MARKET = "market"
    SECTOR = "sector"
    CURRENCY = "currency"
    IDIOSYNCRATIC = "idiosyncratic"


@dataclass(frozen=True)
class FactorExposure:
    """Exposure to a single risk factor."""

    factor: RiskFactor
    factor_name: str
    beta: Decimal
    exposure_value: Decimal
    pct_of_total: Decimal


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
