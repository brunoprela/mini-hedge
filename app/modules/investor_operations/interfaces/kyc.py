"""KYC and fund terms DTOs."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.investor_operations.interfaces.redemption import RedemptionFrequency


class KYCStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class AMLStatus(StrEnum):
    PENDING = "pending"
    CLEARED = "cleared"
    FLAGGED = "flagged"
    BLOCKED = "blocked"


class KYCScreeningResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    approved: bool
    kyc_status: KYCStatus
    aml_status: AMLStatus
    sanctions_clear: bool
    pep_flag: bool
    source_of_funds_verified: bool
    screening_provider: str
    notes: str = ""


class InvestorKYCInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    investor_id: UUID
    kyc_status: KYCStatus
    aml_status: AMLStatus
    sanctions_clear: bool
    pep_flag: bool
    source_of_funds_verified: bool
    accredited_investor: bool
    last_screened_at: datetime | None = None
    screening_expires_at: datetime | None = None
    screening_provider: str | None = None


class FundTermsSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    share_class: str
    lock_up_months: int
    notice_period_days: int
    redemption_frequency: RedemptionFrequency
    gate_pct: Decimal
    minimum_subscription: Decimal
    minimum_redemption: Decimal
    dealing_day: int
    payment_days: int
    is_active: bool
