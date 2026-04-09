"""Subscription request DTOs."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
