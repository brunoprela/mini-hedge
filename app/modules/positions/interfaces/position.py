"""Position value objects and reader protocol."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TradeSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


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


class PortfolioSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    total_market_value: Decimal
    total_cost_basis: Decimal
    total_realized_pnl: Decimal
    total_unrealized_pnl: Decimal
    position_count: int


class FundAggregate(BaseModel):
    """Cross-portfolio KPI summary for a fund."""

    model_config = ConfigDict(frozen=True)

    total_aum: Decimal
    total_realized_pnl: Decimal
    total_unrealized_pnl: Decimal
    portfolio_count: int
    total_positions: int


class TradeRequest(BaseModel):
    """Inbound trade for position entry."""

    portfolio_id: UUID
    instrument_id: str
    side: TradeSide
    quantity: Decimal
    price: Decimal
    currency: str = "USD"
    idempotency_key: str | None = None


class PositionReader(Protocol):
    """Read interface exposed to other modules."""

    async def get_position(
        self,
        portfolio_id: UUID,
        instrument_id: str,
    ) -> Position | None: ...

    async def get_by_portfolio(
        self,
        portfolio_id: UUID,
    ) -> list[Position]: ...

    async def get_lots(
        self,
        portfolio_id: UUID,
        instrument_id: str,
    ) -> list[PositionLot]: ...

    async def get_position_at(
        self,
        portfolio_id: UUID,
        instrument_id: str,
        at: datetime,
    ) -> Position | None: ...

    async def get_portfolio_pnl(
        self,
        portfolio_id: UUID,
        *,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[PnLSummary]: ...
