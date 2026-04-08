"""Fund administrator REST endpoints — simulates external admin provider."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/admin", tags=["Fund Admin"])


class AdminPositionResponse(BaseModel):
    positions: dict[str, str]  # instrument_id -> quantity


class AdminCashResponse(BaseModel):
    balances: dict[str, str]  # currency -> amount


class AdminNAVResponse(BaseModel):
    nav: str
    positions: dict[str, str]
    cash: dict[str, str]


class SubscriptionRegistration(BaseModel):
    request_id: str
    investor_id: str
    amount: str


class SubscriptionRegistrationResponse(BaseModel):
    wire_reference: str


class WireConfirmation(BaseModel):
    wire_reference: str


class RedemptionRegistration(BaseModel):
    request_id: str
    investor_id: str
    amount: str


class PaymentResponse(BaseModel):
    payment_reference: str


def _get_admin_service(request: Request):  # noqa: ANN202
    return request.app.state.fund_admin_service


@router.get("/positions", response_model=AdminPositionResponse)
async def get_admin_positions(request: Request) -> AdminPositionResponse:
    """Return the administrator's independent view of positions."""
    service = _get_admin_service(request)
    positions = service.get_positions()
    return AdminPositionResponse(
        positions={k: str(v) for k, v in positions.items()}
    )


@router.get("/cash", response_model=AdminCashResponse)
async def get_admin_cash(request: Request) -> AdminCashResponse:
    """Return the administrator's independent view of cash balances."""
    service = _get_admin_service(request)
    cash = service.get_cash_balances()
    return AdminCashResponse(
        balances={k: str(v) for k, v in cash.items()}
    )


@router.get("/nav", response_model=AdminNAVResponse)
async def get_admin_nav(request: Request) -> AdminNAVResponse:
    """Return the administrator's independent NAV calculation."""
    service = _get_admin_service(request)
    # Use current market prices from the market data service
    md_service = request.app.state.market_data_service
    prices = {
        iid: snap.mid
        for iid, snap in md_service.latest_prices.items()
        if not iid.startswith("FX:")
    }
    nav = service.get_nav(prices)
    positions = service.get_positions()
    cash = service.get_cash_balances()
    return AdminNAVResponse(
        nav=str(nav),
        positions={k: str(v) for k, v in positions.items()},
        cash={k: str(v) for k, v in cash.items()},
    )


@router.post("/subscriptions", response_model=SubscriptionRegistrationResponse)
async def register_subscription(
    body: SubscriptionRegistration, request: Request
) -> SubscriptionRegistrationResponse:
    """Register a subscription and return a wire reference."""
    service = _get_admin_service(request)
    wire_ref = service.register_subscription(
        body.request_id, body.investor_id, Decimal(body.amount)
    )
    return SubscriptionRegistrationResponse(wire_reference=wire_ref)


@router.post(
    "/subscriptions/{request_id}/confirm-wire",
    response_model=dict,
)
async def confirm_wire(
    request_id: str, body: WireConfirmation, request: Request
) -> dict:
    """Simulate bank wire confirmation."""
    service = _get_admin_service(request)
    ok = service.confirm_wire_receipt(body.wire_reference)
    if not ok:
        raise HTTPException(404, f"Wire reference {body.wire_reference} not found")
    return {"status": "confirmed"}


@router.post("/redemptions", status_code=201)
async def register_redemption(
    body: RedemptionRegistration, request: Request
) -> dict:
    """Register a pending redemption payment."""
    service = _get_admin_service(request)
    service.register_redemption(
        body.request_id, body.investor_id, Decimal(body.amount)
    )
    return {"status": "registered"}


@router.post(
    "/redemptions/{request_id}/send-payment",
    response_model=PaymentResponse,
)
async def send_redemption_payment(
    request_id: str, request: Request
) -> PaymentResponse:
    """Simulate sending a wire out for a redemption."""
    service = _get_admin_service(request)
    pay_ref = service.send_redemption_payment(request_id)
    if pay_ref is None:
        raise HTTPException(404, f"Redemption {request_id} not found")
    return PaymentResponse(payment_reference=pay_ref)
