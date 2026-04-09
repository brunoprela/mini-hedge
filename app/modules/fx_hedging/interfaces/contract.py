"""FX forward contract DTOs and enums."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FXForwardStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    ROLLED = "rolled"
    EXPIRED = "expired"
    SETTLED = "settled"


class FXForwardDirection(StrEnum):
    BUY = "buy"
    SELL = "sell"


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
