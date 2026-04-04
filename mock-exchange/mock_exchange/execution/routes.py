"""Order execution REST endpoints — modeled after Prime Broker / EMS patterns."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(tags=["Execution"])


class SubmitOrderRequest(BaseModel):
    client_order_id: str
    instrument_id: str
    side: str  # buy | sell
    order_type: str  # market | limit
    quantity: str
    limit_price: str | None = None


class OrderResponse(BaseModel):
    exchange_order_id: str
    client_order_id: str
    status: str
    received_at: str
    instrument_id: str
    side: str
    quantity: str
    filled_quantity: str
    avg_fill_price: str | None = None
    fills: list[dict[str, str]]


def _get_engine(request: Request):  # noqa: ANN202
    return request.app.state.execution_engine


@router.post("/orders", response_model=OrderResponse)
async def submit_order(request: Request, body: SubmitOrderRequest) -> OrderResponse:
    """Submit an order for execution."""
    engine = _get_engine(request)
    order = engine.submit_order(
        client_order_id=body.client_order_id,
        instrument_id=body.instrument_id,
        side=body.side,
        order_type=body.order_type,
        quantity=Decimal(body.quantity),
        limit_price=Decimal(body.limit_price) if body.limit_price else None,
    )
    return _order_to_response(order)


@router.get("/orders/{exchange_order_id}", response_model=OrderResponse)
async def get_order(request: Request, exchange_order_id: str) -> OrderResponse:
    """Get order status and fills."""
    engine = _get_engine(request)
    order = engine.get_order(exchange_order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Order {exchange_order_id} not found")
    return _order_to_response(order)


@router.delete("/orders/{exchange_order_id}")
async def cancel_order(request: Request, exchange_order_id: str) -> dict[str, object]:
    """Cancel an order."""
    engine = _get_engine(request)
    success = engine.cancel_order(exchange_order_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot cancel order")
    return {"cancelled": True, "exchange_order_id": exchange_order_id}


def _order_to_response(order: object) -> OrderResponse:
    return OrderResponse(
        exchange_order_id=order.exchange_order_id,  # type: ignore[attr-defined]
        client_order_id=order.client_order_id,  # type: ignore[attr-defined]
        status=order.status,  # type: ignore[attr-defined]
        received_at=order.received_at.isoformat(),  # type: ignore[attr-defined]
        instrument_id=order.instrument_id,  # type: ignore[attr-defined]
        side=order.side,  # type: ignore[attr-defined]
        quantity=str(order.quantity),  # type: ignore[attr-defined]
        filled_quantity=str(order.filled_quantity),  # type: ignore[attr-defined]
        avg_fill_price=str(order.avg_fill_price) if order.avg_fill_price else None,  # type: ignore[attr-defined]
        fills=[
            {
                "fill_id": f.fill_id,
                "quantity": str(f.quantity),
                "price": str(f.price),
                "filled_at": f.filled_at.isoformat(),
            }
            for f in order.fills  # type: ignore[attr-defined]
        ],
    )
