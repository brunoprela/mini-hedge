"""Typed event models for order lifecycle events.

These provide structured, validated payloads instead of generic
``dict[str, Any]`` blobs. They subclass ``BaseEvent`` so they are
fully compatible with ``EventBus.publish()``.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class OrderCreatedData(BaseModel):
    """Payload for ``orders.created`` events."""

    model_config = ConfigDict(frozen=True)

    order_id: str
    portfolio_id: str
    instrument_id: str
    side: str
    order_type: str
    quantity: str
    state: str


class OrderFilledData(BaseModel):
    """Payload for ``orders.filled`` events."""

    model_config = ConfigDict(frozen=True)

    order_id: str
    portfolio_id: str
    instrument_id: str
    side: str
    fill_quantity: str
    fill_price: str
    state: str


class TradeExecutedData(BaseModel):
    """Payload for ``trades.executed`` events."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: str
    instrument_id: str
    side: str
    quantity: str
    price: str
    trade_id: str
    currency: str = "USD"


def order_created_data(
    *,
    order_id: str,
    portfolio_id: str,
    instrument_id: str,
    side: str,
    order_type: str,
    quantity: Decimal,
    state: str,
) -> dict[str, str]:
    """Build a validated ``orders.created`` payload dict."""
    return OrderCreatedData(
        order_id=order_id,
        portfolio_id=portfolio_id,
        instrument_id=instrument_id,
        side=side,
        order_type=order_type,
        quantity=str(quantity),
        state=state,
    ).model_dump()


def order_filled_data(
    *,
    order_id: str,
    portfolio_id: str,
    instrument_id: str,
    side: str,
    fill_quantity: Decimal,
    fill_price: Decimal,
    state: str,
) -> dict[str, str]:
    """Build a validated ``orders.filled`` payload dict."""
    return OrderFilledData(
        order_id=order_id,
        portfolio_id=portfolio_id,
        instrument_id=instrument_id,
        side=side,
        fill_quantity=str(fill_quantity),
        fill_price=str(fill_price),
        state=state,
    ).model_dump()


def trade_executed_data(
    *,
    portfolio_id: str,
    instrument_id: str,
    side: str,
    quantity: Decimal,
    price: Decimal,
    trade_id: str,
    currency: str = "USD",
) -> dict[str, str]:
    """Build a validated ``trades.executed`` payload dict."""
    return TradeExecutedData(
        portfolio_id=portfolio_id,
        instrument_id=instrument_id,
        side=side,
        quantity=str(quantity),
        price=str(price),
        trade_id=trade_id,
        currency=currency,
    ).model_dump()
