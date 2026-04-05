"""Fee accounting public interface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FeeType(StrEnum):
    MANAGEMENT = "management"
    PERFORMANCE = "performance"
    ADMIN = "admin"


class AccrualStatus(StrEnum):
    ACCRUED = "accrued"
    CRYSTALLIZED = "crystallized"
    PAID = "paid"


@dataclass(frozen=True)
class FeeSchedule:
    """Defines the fee structure for a fund."""

    fund_slug: str
    management_fee_bps: int  # e.g., 200 = 2%
    performance_fee_pct: Decimal  # e.g., 20 = 20%
    hurdle_rate_pct: Decimal  # annual hurdle rate, e.g., 0 or 4
    high_water_mark: bool  # whether HWM applies
    crystallization_frequency: str  # "annual", "quarterly"
    payment_frequency: str  # "quarterly", "monthly"


class FeeAccrual(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID | None = None
    portfolio_id: UUID
    fee_type: FeeType
    accrual_date: date
    nav_basis: Decimal
    accrued_amount: Decimal
    cumulative_amount: Decimal
    status: AccrualStatus
    created_at: datetime | None = None


class HighWaterMarkRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID | None = None
    portfolio_id: UUID
    hwm_date: date
    hwm_nav: Decimal
    peak_nav: Decimal
