"""FX hedging recommendation and summary DTOs."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from app.modules.fx_hedging.interfaces.contract import FXForwardContract


class FXHedgingSummary(BaseModel):
    """Portfolio-level FX hedging summary."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    open_forwards: int
    total_notional: Decimal
    total_mtm: Decimal
    currency_breakdown: dict[str, Decimal]
    expiring_within_5d: int
    calculated_at: datetime


class HedgeRecommendationResponse(BaseModel):
    """Hedge recommendation for API response."""

    model_config = ConfigDict(frozen=True)

    currency_pair: str
    base_currency: str
    quote_currency: str
    notional: Decimal
    direction: str
    hedge_ratio: Decimal
    tenor_days: int
    estimated_forward: Decimal
    estimated_cost_bps: Decimal


class RollRecommendation(BaseModel):
    """Roll recommendation for an expiring forward."""

    model_config = ConfigDict(frozen=True)

    forward_id: UUID
    maturity_date: date
    days_remaining: int
    current_mtm: Decimal
    suggested_new_tenor_days: int
    estimated_roll_cost_bps: Decimal


class FXHedgingReader(Protocol):
    """Public read interface for other modules (e.g., exposure)."""

    async def get_open_forwards(
        self,
        portfolio_id: UUID,
    ) -> list[FXForwardContract]: ...

    async def get_summary(
        self,
        portfolio_id: UUID,
    ) -> FXHedgingSummary | None: ...
