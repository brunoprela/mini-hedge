"""Reconciliation DTOs and enums."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BreakType(StrEnum):
    QUANTITY_MISMATCH = "quantity_mismatch"
    MISSING_INTERNAL = "missing_internal"
    MISSING_BROKER = "missing_broker"
    MISSING_ADMIN = "missing_admin"
    BROKER_ADMIN_MISMATCH = "broker_admin_mismatch"
    INTERNAL_ADMIN_MISMATCH = "internal_admin_mismatch"
    CASH_MISMATCH = "cash_mismatch"


class BreakStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class SLAStatus(StrEnum):
    WITHIN_SLA = "within_sla"
    WARNING = "warning"
    BREACHED = "breached"


class ReconciliationBreak(BaseModel):
    model_config = ConfigDict(frozen=True)

    instrument_id: str
    break_type: BreakType
    internal_quantity: Decimal
    broker_quantity: Decimal
    admin_quantity: Decimal | None = None
    difference: Decimal
    is_material: bool


class CashBreak(BaseModel):
    """Cash reconciliation break between internal and admin cash."""

    model_config = ConfigDict(frozen=True)

    currency: str
    internal_balance: Decimal
    admin_balance: Decimal
    difference: Decimal
    is_material: bool


class ReconciliationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    business_date: date
    total_positions: int
    matched_positions: int
    breaks: list[ReconciliationBreak]
    cash_breaks: list[CashBreak] = []
    is_clean: bool
    reconciled_at: datetime


class AutoResolutionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    auto_resolved: int
    auto_escalated: int
    rules_applied: list[str]


class AgingBucket(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: str
    count: int
    total_difference: Decimal


class AgingSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    buckets: list[AgingBucket]
    oldest_break_hours: float
    sla_breached_count: int


class TrackedBreak(BaseModel):
    """A reconciliation break with resolution lifecycle."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    portfolio_id: UUID
    business_date: date
    instrument_id: str | None = None
    break_type: BreakType
    internal_quantity: Decimal
    broker_quantity: Decimal
    admin_quantity: Decimal | None = None
    difference: Decimal
    is_material: bool
    currency: str | None = None
    internal_balance: Decimal | None = None
    admin_balance: Decimal | None = None
    status: BreakStatus
    assigned_to: str | None = None
    resolution_note: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None
