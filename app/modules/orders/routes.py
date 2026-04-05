"""FastAPI routes for the orders module."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orders.dependencies import get_order_service
from app.modules.orders.interface import (
    CreateOrderRequest,
    FillDetail,
    OrderSummary,
)
from app.modules.orders.order_service import OrderService
from app.modules.orders.state_machine import InvalidTransitionError
from app.shared.auth import Permission, require_permission
from app.shared.database import get_db
from app.shared.request_context import RequestContext

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderSummary, status_code=201)
async def create_order(
    body: CreateOrderRequest,
    request_context: RequestContext = require_permission(Permission.ORDERS_CREATE),
    order_service: OrderService = Depends(get_order_service),
    session: AsyncSession = Depends(get_db),
) -> OrderSummary:
    return await order_service.create_order(
        request=body,
        fund_slug=request_context.fund_slug,
        actor_id=request_context.actor_id,
        session=session,
    )


@router.get("", response_model=list[OrderSummary])
async def list_orders(
    portfolio_id: UUID = Query(...),
    state: str | None = Query(None),
    request_context: RequestContext = require_permission(Permission.ORDERS_READ),
    order_service: OrderService = Depends(get_order_service),
    session: AsyncSession = Depends(get_db),
) -> list[OrderSummary]:
    return await order_service.get_orders(portfolio_id, state=state, session=session)


@router.get("/{order_id}", response_model=OrderSummary)
async def get_order(
    order_id: UUID,
    request_context: RequestContext = require_permission(Permission.ORDERS_READ),
    order_service: OrderService = Depends(get_order_service),
    session: AsyncSession = Depends(get_db),
) -> OrderSummary:
    try:
        return await order_service.get_order(order_id, session=session)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{order_id}/fills", response_model=list[FillDetail])
async def get_fills(
    order_id: UUID,
    request_context: RequestContext = require_permission(Permission.ORDERS_READ),
    order_service: OrderService = Depends(get_order_service),
    session: AsyncSession = Depends(get_db),
) -> list[FillDetail]:
    return await order_service.get_fills(order_id, session=session)


@router.post("/{order_id}/cancel", response_model=OrderSummary)
async def cancel_order(
    order_id: UUID,
    request_context: RequestContext = require_permission(Permission.ORDERS_CANCEL),
    order_service: OrderService = Depends(get_order_service),
    session: AsyncSession = Depends(get_db),
) -> OrderSummary:
    try:
        return await order_service.cancel_order(
            order_id, actor_id=request_context.actor_id, session=session
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
