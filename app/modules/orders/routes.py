"""FastAPI routes for the orders module."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.orders.dependencies import get_order_service
from app.modules.orders.interface import (
    CreateOrderRequest,
    FillDetail,
    OrderSummary,
)
from app.modules.orders.service import OrderService
from app.modules.orders.state_machine import InvalidTransitionError
from app.shared.auth import Permission, require_permission
from app.shared.request_context import RequestContext

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderSummary, status_code=201)
async def create_order(
    body: CreateOrderRequest,
    ctx: RequestContext = require_permission(Permission.ORDERS_CREATE),
    service: OrderService = Depends(get_order_service),
) -> OrderSummary:
    return await service.create_order(
        request=body,
        fund_slug=ctx.fund_slug,
        actor_id=ctx.actor_id,
    )


@router.get("", response_model=list[OrderSummary])
async def list_orders(
    portfolio_id: UUID = Query(...),
    state: str | None = Query(None),
    ctx: RequestContext = require_permission(Permission.ORDERS_READ),
    service: OrderService = Depends(get_order_service),
) -> list[OrderSummary]:
    return await service.get_orders(portfolio_id, state=state)


@router.get("/{order_id}", response_model=OrderSummary)
async def get_order(
    order_id: UUID,
    ctx: RequestContext = require_permission(Permission.ORDERS_READ),
    service: OrderService = Depends(get_order_service),
) -> OrderSummary:
    try:
        return await service.get_order(order_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{order_id}/fills", response_model=list[FillDetail])
async def get_fills(
    order_id: UUID,
    ctx: RequestContext = require_permission(Permission.ORDERS_READ),
    service: OrderService = Depends(get_order_service),
) -> list[FillDetail]:
    return await service.get_fills(order_id)


@router.post("/{order_id}/cancel", response_model=OrderSummary)
async def cancel_order(
    order_id: UUID,
    ctx: RequestContext = require_permission(Permission.ORDERS_CANCEL),
    service: OrderService = Depends(get_order_service),
) -> OrderSummary:
    try:
        return await service.cancel_order(order_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
