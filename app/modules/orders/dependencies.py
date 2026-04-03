"""FastAPI dependency wrappers for the orders module."""

from fastapi import HTTPException, Request

from app.modules.orders.service import OrderService


def get_order_service(request: Request) -> OrderService:
    service: OrderService | None = getattr(request.app.state, "order_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="OrderService not initialized",
        )
    return service
