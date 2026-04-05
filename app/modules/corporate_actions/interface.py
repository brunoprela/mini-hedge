"""Corporate actions module public interface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ActionType(StrEnum):
    DIVIDEND = "dividend"
    STOCK_SPLIT = "stock_split"
    REVERSE_SPLIT = "reverse_split"
    SPINOFF = "spinoff"


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class PositionAdjustment:
    """Adjustment to apply to a position from a corporate action."""

    instrument_id: str
    quantity_delta: Decimal
    cost_basis_adjustment: Decimal
    cash_amount: Decimal  # positive = credit, negative = debit


class ProcessedAction(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID | None = None
    action_id: str
    instrument_id: str
    action_type: ActionType
    ex_date: date
    status: ProcessingStatus
    adjustments: list[PositionAdjustment] = []
    processed_at: datetime | None = None
    error_message: str | None = None
