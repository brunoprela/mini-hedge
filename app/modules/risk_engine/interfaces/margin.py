"""Margin management DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MarginSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    business_date: datetime
    initial_margin: Decimal
    maintenance_margin: Decimal
    margin_available: Decimal
    margin_excess_deficit: Decimal
    margin_utilization_pct: Decimal
    margin_call_triggered: bool
    position_margins: list[dict] = []


@dataclass(frozen=True)
class PositionMargin:
    instrument_id: str
    market_value: Decimal
    margin_rate: Decimal  # percentage (e.g. 0.50 = 50%)
    initial_margin: Decimal
    maintenance_margin: Decimal
