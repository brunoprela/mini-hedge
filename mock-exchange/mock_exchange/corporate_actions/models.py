"""Pydantic models for corporate actions."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel


class CorporateActionType(StrEnum):
    DIVIDEND = "dividend"
    STOCK_SPLIT = "stock_split"
    MERGER = "merger"


class CorporateAction(BaseModel):
    action_id: str
    instrument_id: str
    action_type: CorporateActionType
    ex_date: date
    record_date: date | None = None
    pay_date: date | None = None
    amount: str | None = None  # decimal as string for JSON safety
    currency: str = "USD"
    ratio: str | None = None  # e.g. "2:1" for stock splits
    status: str = "pending"
