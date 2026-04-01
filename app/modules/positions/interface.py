"""Position keeping public interface — Protocol + value objects.

Other modules depend ONLY on this file, never on internals.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Position(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    instrument_id: str
    quantity: Decimal
    avg_cost: Decimal
    cost_basis: Decimal
    market_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    currency: str
    last_updated: datetime


class PositionLot(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    portfolio_id: UUID
    instrument_id: str
    quantity: Decimal
    original_quantity: Decimal
    price: Decimal
    acquired_at: datetime
    trade_id: UUID


class PnLSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    date: date
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
    currency: str


class TradeRequest(BaseModel):
    """Inbound trade for position entry."""

    portfolio_id: UUID
    instrument_id: str
    side: str  # "buy" or "sell"
    quantity: Decimal
    price: Decimal
    currency: str = "USD"


class PositionReader(Protocol):
    """Read interface exposed to other modules."""

    async def get_position(
        self,
        portfolio_id: UUID,
        instrument_id: str,
    ) -> Position | None: ...

    async def get_portfolio_positions(
        self,
        portfolio_id: UUID,
    ) -> list[Position]: ...
