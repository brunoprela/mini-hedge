"""EOD processing — Pydantic DTOs and enums."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EODStepName(StrEnum):
    MARKET_CLOSE = "market_close"
    PRICE_FINALIZATION = "price_finalization"
    POSITION_RECON = "position_recon"
    NAV_CALCULATION = "nav_calculation"
    PNL_SNAPSHOT = "pnl_snapshot"
    EOD_RISK = "eod_risk"
    PERFORMANCE_ATTRIBUTION = "performance_attribution"


class EODStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# --- Price Finalization ---


class FinalizedPrice(BaseModel):
    model_config = ConfigDict(frozen=True)

    instrument_id: str
    business_date: date
    close_price: Decimal
    source: str
    finalized_at: datetime
    finalized_by: str


class PriceFinalizationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    business_date: date
    total_instruments: int
    finalized_count: int
    missing_count: int
    missing_instruments: list[str]
    is_complete: bool


# --- NAV ---


class NAVSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    business_date: date
    gross_market_value: Decimal
    net_market_value: Decimal
    cash_balance: Decimal
    accrued_fees: Decimal
    nav: Decimal
    nav_per_share: Decimal
    shares_outstanding: Decimal
    currency: str
    computed_at: datetime


# --- P&L Snapshot ---


class PnLSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    business_date: date
    total_realized_pnl: Decimal
    total_unrealized_pnl: Decimal
    total_pnl: Decimal
    position_count: int
    computed_at: datetime


# --- Reconciliation ---


class BreakType(StrEnum):
    QUANTITY_MISMATCH = "quantity_mismatch"
    MISSING_INTERNAL = "missing_internal"
    MISSING_BROKER = "missing_broker"


class ReconciliationBreak(BaseModel):
    model_config = ConfigDict(frozen=True)

    instrument_id: str
    break_type: BreakType
    internal_quantity: Decimal
    broker_quantity: Decimal
    difference: Decimal
    is_material: bool


class ReconciliationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    business_date: date
    total_positions: int
    matched_positions: int
    breaks: list[ReconciliationBreak]
    is_clean: bool
    reconciled_at: datetime


# --- EOD Run ---


class EODStepResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    step: EODStepName
    status: EODStepStatus
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    details: dict | None = None


class EODRunResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: UUID
    business_date: date
    fund_slug: str
    started_at: datetime
    completed_at: datetime | None = None
    steps: list[EODStepResult]
    is_successful: bool


class EODRunSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: UUID
    business_date: date
    fund_slug: str
    started_at: datetime
    completed_at: datetime | None = None
    is_successful: bool
    steps_completed: int
    steps_total: int
