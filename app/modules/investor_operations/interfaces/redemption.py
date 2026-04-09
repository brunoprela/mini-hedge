"""Redemption request and gate DTOs."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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


class QueueSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    pending_subscriptions: int
    pending_redemptions: int
    total_subscription_amount: Decimal
    total_redemption_amount: Decimal
    next_dealing_date: date | None = None


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
