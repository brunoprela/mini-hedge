"""Investor operations — Pydantic DTOs and enums."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# State enums
# ---------------------------------------------------------------------------


class SubscriptionState(StrEnum):
    DRAFT = "draft"
    PENDING_KYC = "pending_kyc"
    KYC_APPROVED = "kyc_approved"
    KYC_REJECTED = "kyc_rejected"
    PENDING_OPS_REVIEW = "pending_ops_review"
    PENDING_GP_APPROVAL = "pending_gp_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING_WIRE = "pending_wire"
    WIRE_CONFIRMED = "wire_confirmed"
    QUEUED_FOR_NAV = "queued_for_nav"
    EXECUTED = "executed"
    CANCELLED = "cancelled"


class RedemptionState(StrEnum):
    DRAFT = "draft"
    PENDING_VALIDATION = "pending_validation"
    VALIDATED = "validated"
    VALIDATION_FAILED = "validation_failed"
    PENDING_GATE_CHECK = "pending_gate_check"
    GATE_APPLIED = "gate_applied"
    QUEUED_FOR_NAV = "queued_for_nav"
    NAV_CALCULATED = "nav_calculated"
    PENDING_PAYMENT = "pending_payment"
    PAYMENT_SENT = "payment_sent"
    EXECUTED = "executed"
    CANCELLED = "cancelled"


class RedemptionFrequency(StrEnum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


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


# ---------------------------------------------------------------------------
# KYC DTOs
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Fund terms DTOs
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Gate engine DTOs
# ---------------------------------------------------------------------------


class GateAllocation(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_id: UUID
    original_amount: Decimal
    approved_amount: Decimal
    proration_pct: Decimal


class GateCheckResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    gate_triggered: bool
    total_requested: Decimal
    total_approved: Decimal
    gate_capacity: Decimal
    allocations: list[GateAllocation]


# ---------------------------------------------------------------------------
# Subscription request DTOs
# ---------------------------------------------------------------------------


class SubscriptionRequestSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    investor_id: UUID
    share_class: str
    requested_amount: Decimal
    state: SubscriptionState
    submitted_at: datetime
    kyc_decision_at: datetime | None = None
    kyc_decision_by: str | None = None
    ops_decision_at: datetime | None = None
    ops_decision_by: str | None = None
    gp_decision_at: datetime | None = None
    gp_decision_by: str | None = None
    wire_confirmed_at: datetime | None = None
    wire_reference: str | None = None
    dealing_date: date | None = None
    executed_at: datetime | None = None
    nav_per_share: Decimal | None = None
    shares_issued: Decimal | None = None
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Redemption request DTOs
# ---------------------------------------------------------------------------


class RedemptionRequestSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    investor_id: UUID
    requested_amount: Decimal
    approved_amount: Decimal | None = None
    state: RedemptionState
    submitted_at: datetime
    notice_date: date
    earliest_redemption_date: date | None = None
    lock_up_expiry_date: date | None = None
    gate_applied: bool = False
    gate_pct: Decimal | None = None
    dealing_date: date | None = None
    nav_per_share: Decimal | None = None
    shares_redeemed: Decimal | None = None
    payment_due_date: date | None = None
    payment_sent_at: datetime | None = None
    payment_reference: str | None = None
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Queue summary
# ---------------------------------------------------------------------------


class QueueSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    pending_subscriptions: int
    pending_redemptions: int
    total_subscription_amount: Decimal
    total_redemption_amount: Decimal
    next_dealing_date: date | None = None
