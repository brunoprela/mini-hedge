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
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class TimeInForce(StrEnum):
    DAY = "day"
    GTC = "gtc"  # good till cancelled
    IOC = "ioc"  # immediate or cancel
    FOK = "fok"  # fill or kill


class OrderState(StrEnum):
    DRAFT = "draft"
    PENDING_COMPLIANCE = "pending_compliance"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
    WORKING = "working"  # parent algo order: actively spawning children
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"


class AlgoType(StrEnum):
    TWAP = "twap"
    VWAP = "vwap"
    ICEBERG = "iceberg"


class AlgoParams(BaseModel):
    model_config = ConfigDict(frozen=True)

    duration_seconds: int = 7200
    num_slices: int = 200
    visible_quantity: Decimal | None = None
    volume_profile: list[Decimal] | None = None


class CreateOrderRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    instrument_id: str
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    quantity: Decimal
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: TimeInForce = TimeInForce.DAY


class CreateAlgoOrderRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    instrument_id: str
    side: OrderSide
    order_type: OrderType = OrderType.LIMIT
    quantity: Decimal
    limit_price: Decimal | None = None
    time_in_force: TimeInForce = TimeInForce.DAY
    algo_type: AlgoType
    algo_params: AlgoParams = AlgoParams()


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
    stop_price: Decimal | None = None
    avg_fill_price: Decimal | None
    state: OrderState
    rejection_reason: str | None
    compliance_results: list[dict[str, object]] | None
    time_in_force: TimeInForce
    created_at: datetime
    updated_at: datetime
    # Algo fields (None for regular orders)
    algo_type: AlgoType | None = None
    algo_params: dict[str, object] | None = None
    is_parent: bool = False
    parent_order_id: UUID | None = None
    children_count: int = 0
    children_filled: int = 0
    # Multi-broker routing
    broker_id: str | None = None


class FillDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    order_id: UUID
    quantity: Decimal
    price: Decimal
    broker_id: str | None = None
    commission: Decimal | None = None
    venue: str | None = None
    filled_at: datetime


# ---------------------------------------------------------------------------
#  Multi-broker routing types
# ---------------------------------------------------------------------------


class BrokerScorecard(BaseModel):
    model_config = ConfigDict(frozen=True)

    broker_id: str
    instrument_class: str | None = None
    total_orders: int = 0
    total_fills: int = 0
    total_rejects: int = 0
    avg_slippage_bps: Decimal = Decimal("0")
    avg_fill_time_ms: int = 0
    avg_cost_bps: Decimal = Decimal("0")
    fill_rate: Decimal = Decimal("0")


class RoutingRule(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    fund_slug: str
    strategy: str | None = None
    instrument_class: str | None = None
    min_size: Decimal | None = None
    max_size: Decimal | None = None
    preferred_broker_id: str
    priority: int = 0
    is_active: bool = True


class CreateRoutingRuleRequest(BaseModel):
    fund_slug: str
    strategy: str | None = None
    instrument_class: str | None = None
    min_size: Decimal | None = None
    max_size: Decimal | None = None
    preferred_broker_id: str
    priority: int = 0


class RoutingDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    broker_id: str
    quantity: Decimal
    score: Decimal | None = None
    score_breakdown: dict[str, object] | None = None
    decision_reason: str | None = None


class BestExecutionReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    fund_slug: str
    period_start: datetime
    period_end: datetime
    total_orders: int
    broker_breakdown: list[dict[str, object]]
    avg_slippage_bps: Decimal
    avg_cost_bps: Decimal
