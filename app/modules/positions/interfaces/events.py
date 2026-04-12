"""Position domain events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.modules.positions.interfaces.position import TradeSide


class PositionEventType(StrEnum):
    TRADE_BUY = "trade.buy"
    TRADE_SELL = "trade.sell"
    STOCK_SPLIT = "stock.split"
    DIVIDEND_PAID = "dividend.paid"
    POSITION_CHANGED = "position.changed"
    PNL_REALIZED = "pnl.realized"
    PNL_MARK_TO_MARKET = "pnl.mark_to_market"


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
class CorporateActionEventData:
    """Payload for corporate action events (splits, dividends)."""

    portfolio_id: UUID
    instrument_id: str
    currency: str
    action_id: UUID
    # For splits: new_shares / old_shares (e.g. 2.0 for 2-for-1)
    split_ratio: Decimal = Decimal(1)
    # For dividends: total cash amount for this position
    dividend_amount: Decimal = Decimal(0)


@dataclass(frozen=True)
class TradeEvent:
    """A trade event applied to the position aggregate."""

    event_type: PositionEventType
    timestamp: datetime
    data: TradeEventData | CorporateActionEventData


@dataclass(frozen=True)
class PositionChangedData:
    """Payload for a position.changed downstream event."""

    portfolio_id: UUID
    instrument_id: str
    quantity: Decimal
    avg_cost: Decimal
    cost_basis: Decimal
    currency: str


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
    currency: str


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
    currency: str


@dataclass(frozen=True)
class PnLMarkToMarket:
    """Downstream event: unrealized P&L changed via mark-to-market."""

    event_type: PositionEventType  # = PNL_MARK_TO_MARKET
    data: PnLMarkToMarketData


DownstreamEvent = PositionChanged | PnLRealized | PnLMarkToMarket
