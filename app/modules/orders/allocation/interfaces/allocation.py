"""Block trade allocation — cross-fund fill distribution DTOs."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.orders.interfaces import AlgoParams, AlgoType, OrderSide, OrderType


class AllocationState(StrEnum):
    DRAFT = "draft"
    PENDING_COMPLIANCE = "pending_compliance"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    ALLOCATED = "allocated"
    CANCELLED = "cancelled"


class AllocationLegRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    fund_slug: str
    portfolio_id: UUID
    target_pct: Decimal


class CreateBlockAllocationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    instrument_id: str
    side: OrderSide
    total_quantity: Decimal
    order_type: OrderType = OrderType.MARKET
    limit_price: Decimal | None = None
    algo_type: AlgoType | None = None
    algo_params: AlgoParams | None = None
    legs: list[AllocationLegRequest]


class AllocationLegSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    fund_slug: str
    portfolio_id: UUID
    target_pct: Decimal
    target_quantity: Decimal
    filled_quantity: Decimal
    avg_fill_price: Decimal | None
    state: str


class BlockAllocationSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    instrument_id: str
    side: str
    total_quantity: Decimal
    filled_quantity: Decimal
    avg_fill_price: Decimal | None
    state: AllocationState
    algo_type: AlgoType | None = None
    legs: list[AllocationLegSummary]
    created_by: str
    created_at: datetime
