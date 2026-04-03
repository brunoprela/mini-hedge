"""Order management public interface — Protocol + value objects."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


class TimeInForce(StrEnum):
    DAY = "day"
    GTC = "gtc"  # good till cancelled
    IOC = "ioc"  # immediate or cancel


class OrderState(StrEnum):
    DRAFT = "draft"
    PENDING_COMPLIANCE = "pending_compliance"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"


class CreateOrderRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    instrument_id: str
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    quantity: Decimal
    limit_price: Decimal | None = None
    time_in_force: TimeInForce = TimeInForce.DAY


class OrderSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    portfolio_id: UUID
    instrument_id: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    filled_quantity: Decimal
    limit_price: Decimal | None
    avg_fill_price: Decimal | None
    state: OrderState
    rejection_reason: str | None
    compliance_results: list[dict] | None
    time_in_force: TimeInForce
    created_at: datetime
    updated_at: datetime


class FillDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    order_id: UUID
    quantity: Decimal
    price: Decimal
    filled_at: datetime
