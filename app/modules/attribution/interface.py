"""Performance attribution public interface — Protocol + value objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AttributionMethod(StrEnum):
    BRINSON_FACHLER = "brinson_fachler"
    RISK_BASED = "risk_based"


# ---------------------------------------------------------------------------
# Internal value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SectorAttribution:
    """Brinson-Fachler attribution for a single sector."""

    sector: str
    portfolio_weight: Decimal
    benchmark_weight: Decimal
    portfolio_return: Decimal
    benchmark_return: Decimal
    allocation_effect: Decimal
    selection_effect: Decimal
    interaction_effect: Decimal
    total_effect: Decimal


@dataclass(frozen=True)
class RiskFactorAttribution:
    """Risk-based P&L attribution for a single factor."""

    factor: str
    factor_return: Decimal
    portfolio_exposure: Decimal
    pnl_contribution: Decimal
    pct_of_total: Decimal


# ---------------------------------------------------------------------------
# API / read-model value objects (Pydantic)
# ---------------------------------------------------------------------------


class BrinsonFachlerResult(BaseModel):
    """Complete Brinson-Fachler attribution result."""

    model_config = ConfigDict(frozen=True)

    id: UUID | None = None
    portfolio_id: UUID
    period_start: date
    period_end: date
    portfolio_return: Decimal
    benchmark_return: Decimal
    active_return: Decimal
    total_allocation: Decimal
    total_selection: Decimal
    total_interaction: Decimal
    sectors: list[SectorAttribution] = []
    calculated_at: datetime


class RiskBasedResult(BaseModel):
    """Risk-based P&L attribution result."""

    model_config = ConfigDict(frozen=True)

    id: UUID | None = None
    portfolio_id: UUID
    period_start: date
    period_end: date
    total_pnl: Decimal
    systematic_pnl: Decimal
    idiosyncratic_pnl: Decimal
    systematic_pct: Decimal
    factor_contributions: list[RiskFactorAttribution] = []
    calculated_at: datetime


class CumulativeAttribution(BaseModel):
    """Multi-period cumulative attribution using Carino linking."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    period_start: date
    period_end: date
    cumulative_portfolio_return: Decimal
    cumulative_benchmark_return: Decimal
    cumulative_active_return: Decimal
    cumulative_allocation: Decimal
    cumulative_selection: Decimal
    cumulative_interaction: Decimal
    periods: list[BrinsonFachlerResult] = []
    calculated_at: datetime


# ---------------------------------------------------------------------------
# Module protocol
# ---------------------------------------------------------------------------


class AttributionReader(Protocol):
    """Public read interface for other modules."""

    async def get_brinson_fachler(
        self,
        portfolio_id: UUID,
        start: date,
        end: date,
    ) -> BrinsonFachlerResult: ...

    async def get_risk_based(
        self,
        portfolio_id: UUID,
        start: date,
        end: date,
    ) -> RiskBasedResult: ...

    async def get_cumulative(
        self,
        portfolio_id: UUID,
        start: date,
        end: date,
    ) -> CumulativeAttribution: ...
