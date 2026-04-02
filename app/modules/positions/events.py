"""Typed domain events emitted by the positions module.

These replace inline dicts in handlers.py with structured, validated schemas.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.modules.positions.interface import PositionEventType, TradeSide


class TradeEventData(BaseModel):
    """Payload for a trade event (buy or sell)."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: str
    instrument_id: str
    side: TradeSide
    quantity: Decimal
    price: Decimal
    trade_id: str
    currency: str


class TradeEvent(BaseModel):
    """A trade event to be applied to the position aggregate."""

    model_config = ConfigDict(frozen=True)

    event_type: PositionEventType
    timestamp: str
    data: TradeEventData


class PositionChangedData(BaseModel):
    """Payload for a position.changed downstream event."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: str
    instrument_id: str
    quantity: str
    avg_cost: str
    cost_basis: str
    currency: str


class PnLRealizedData(BaseModel):
    """Payload for a pnl.realized downstream event."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: str
    instrument_id: str
    realized_pnl: str
    trade_id: str
    currency: str
