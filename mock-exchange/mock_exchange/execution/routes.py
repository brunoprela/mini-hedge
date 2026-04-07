"""Order execution REST endpoints — modeled after Prime Broker / EMS patterns."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from mock_exchange.execution.brokers import get_all_brokers, get_broker
from mock_exchange.shared.models import BrokerInfo

router = APIRouter(tags=["Execution"])


class SubmitOrderRequest(BaseModel):
    client_order_id: str
    instrument_id: str
    side: str  # buy | sell
    order_type: str  # market | limit
    quantity: str
    limit_price: str | None = None
    broker_id: str = "GS"


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
    broker_id: str | None = None
    arrival_price: str | None = None
    fills: list[dict[str, str]]


def _get_engine(request: Request):  # noqa: ANN202
    return request.app.state.execution_engine


@router.get("/orders", response_model=list[OrderResponse])
async def list_orders(request: Request) -> list[OrderResponse]:
    """List all orders — used by EOD reconciliation to build broker position view."""
    engine = _get_engine(request)
    return [_order_to_response(o) for o in engine.get_all_orders()]


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
        broker_id=body.broker_id,
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


@router.get("/brokers", response_model=list[BrokerInfo])
async def list_brokers() -> list[BrokerInfo]:
    """List available broker profiles."""
    return [
        BrokerInfo(
            broker_id=b.broker_id,
            name=b.name,
            commission_bps=b.commission_bps,
            latency_ms=b.latency_ms,
            fill_rate=b.fill_rate,
            sector_specializations=list(b.sector_specializations),
        )
        for b in get_all_brokers()
    ]


@router.get("/brokers/{broker_id}", response_model=BrokerInfo)
async def get_broker_detail(broker_id: str) -> BrokerInfo:
    """Get broker profile details."""
    b = get_broker(broker_id)
    if b is None:
        raise HTTPException(status_code=404, detail=f"Broker {broker_id} not found")
    return BrokerInfo(
        broker_id=b.broker_id,
        name=b.name,
        commission_bps=b.commission_bps,
        latency_ms=b.latency_ms,
        fill_rate=b.fill_rate,
        sector_specializations=list(b.sector_specializations),
    )


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
        broker_id=getattr(order, "broker_id", None),
        arrival_price=str(order.arrival_price) if getattr(order, "arrival_price", None) else None,  # type: ignore[attr-defined]
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
