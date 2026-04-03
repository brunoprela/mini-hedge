"""Position keeping public interface — Protocol + value objects.

Other modules depend ONLY on this file, never on internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TradeSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class PositionEventType(StrEnum):
    TRADE_BUY = "trade.buy"
    TRADE_SELL = "trade.sell"
    POSITION_CHANGED = "position.changed"
    PNL_REALIZED = "pnl.realized"
    PNL_MARK_TO_MARKET = "pnl.mark_to_market"


# ---------------------------------------------------------------------------
# Typed domain events (frozen dataclasses — no serialization concern)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TradeEventData:
    """Payload for a trade event (buy or sell)."""

    portfolio_id: UUID
    instrument_id: str
    side: TradeSide
    quantity: Decimal
    price: Decimal
    trade_id: UUID
    currency: str


@dataclass(frozen=True)
class TradeEvent:
    """A trade event applied to the position aggregate."""

    event_type: PositionEventType
    timestamp: datetime
    data: TradeEventData


@dataclass(frozen=True)
class PositionChangedData:
    """Payload for a position.changed downstream event."""

    portfolio_id: UUID
    instrument_id: str
    quantity: Decimal
    avg_cost: Decimal
    cost_basis: Decimal


@dataclass(frozen=True)
class PositionChanged:
    """Downstream event: position state changed."""

    event_type: PositionEventType  # = POSITION_CHANGED
    data: PositionChangedData


@dataclass(frozen=True)
class PnLRealizedData:
    """Payload for a pnl.realized downstream event."""

    portfolio_id: UUID
    instrument_id: str
    realized_pnl: Decimal
    price: Decimal


@dataclass(frozen=True)
class PnLRealized:
    """Downstream event: P&L was realized from a trade."""

    event_type: PositionEventType  # = PNL_REALIZED
    data: PnLRealizedData


@dataclass(frozen=True)
class PnLMarkToMarketData:
    """Payload for a pnl.mark_to_market downstream event."""

    portfolio_id: UUID
    instrument_id: str
    market_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    pnl_change: Decimal


@dataclass(frozen=True)
class PnLMarkToMarket:
    """Downstream event: unrealized P&L changed via mark-to-market."""

    event_type: PositionEventType  # = PNL_MARK_TO_MARKET
    data: PnLMarkToMarketData


DownstreamEvent = PositionChanged | PnLRealized | PnLMarkToMarket


# ---------------------------------------------------------------------------
# API / read-model value objects (Pydantic — serialization boundary)
# ---------------------------------------------------------------------------


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
    side: TradeSide
    quantity: Decimal
    price: Decimal
    currency: str = "USD"


# ---------------------------------------------------------------------------
# Module protocol — the public read interface for other modules
# ---------------------------------------------------------------------------


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
