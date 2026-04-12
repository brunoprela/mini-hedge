"""KYC and fund terms DTOs."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.investor_operations.interfaces.redemption import RedemptionFrequency
from app.shared.adapters.kyc import AMLStatus, KYCScreeningResult, KYCStatus

# Re-export so existing consumers within investor_operations keep working.
__all__ = [
    "AMLStatus",
    "FundTermsSummary",
    "InvestorKYCInfo",
    "KYCScreeningResult",
    "KYCStatus",
]


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
