"""EOD run-related DTOs and enums."""

from __future__ import annotations

from datetime import date, datetime
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
    FEE_ACCRUAL = "fee_accrual"
    CAPITAL_ALLOCATION = "capital_allocation"
    DEALING_DATE_EXECUTION = "dealing_date_execution"
    PERFORMANCE_ATTRIBUTION = "performance_attribution"


class EODStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class EODStepResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    step: EODStepName
    status: EODStepStatus
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    details: dict[str, object] | None = None


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
