"""FX hedging public interface — enums, value objects, and API models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FXForwardStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    ROLLED = "rolled"
    EXPIRED = "expired"
    SETTLED = "settled"


class FXForwardDirection(StrEnum):
    BUY = "buy"
    SELL = "sell"


# ---------------------------------------------------------------------------
# API models (Pydantic — serialization boundary)
# ---------------------------------------------------------------------------


class FXForwardContract(BaseModel):
    """An FX forward contract."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    portfolio_id: UUID
    base_currency: str
    quote_currency: str
    direction: FXForwardDirection
    notional: Decimal
    contract_rate: Decimal
    spot_at_inception: Decimal
    trade_date: date
    maturity_date: date
    status: FXForwardStatus
    counterparty: str | None = None
    roll_from_id: UUID | None = None
    mtm_value: Decimal | None = None
    mtm_timestamp: datetime | None = None
    created_at: datetime | None = None


class FXForwardCreate(BaseModel):
    """Request to open a new FX forward."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    base_currency: str
    quote_currency: str
    direction: FXForwardDirection
    notional: Decimal
    contract_rate: Decimal
    spot_at_inception: Decimal
    trade_date: date
    maturity_date: date
    counterparty: str | None = None


class FXForwardClose(BaseModel):
    """Request to close an existing FX forward."""

    model_config = ConfigDict(frozen=True)

    close_rate: Decimal
    close_spot: Decimal


class FXForwardRoll(BaseModel):
    """Request to roll a forward to a new maturity."""

    model_config = ConfigDict(frozen=True)

    new_maturity_date: date
    new_contract_rate: Decimal
    current_spot: Decimal


class FXInterestRate(BaseModel):
    """Interest rate for a currency (simplified — no yield curve)."""

    model_config = ConfigDict(frozen=True)

    currency: str
    rate: Decimal
    tenor_days: int
    source: str
    updated_at: datetime


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


# ---------------------------------------------------------------------------
# Module protocol — read interface for other modules
# ---------------------------------------------------------------------------


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
