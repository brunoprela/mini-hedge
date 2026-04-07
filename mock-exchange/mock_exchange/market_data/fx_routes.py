"""FX and yield curve REST endpoints for mock exchange."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

if TYPE_CHECKING:
    from mock_exchange.market_data.fx_forward import FXForwardService
    from mock_exchange.market_data.yield_curve import YieldCurveSimulator

router = APIRouter(tags=["FX & Yield Curves"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class CurvePointResponse(BaseModel):
    tenor_days: int
    tenor_label: str
    rate: float


class YieldCurveResponse(BaseModel):
    currency: str
    points: list[CurvePointResponse]
    timestamp: str


class ForwardQuoteResponse(BaseModel):
    base_currency: str
    quote_currency: str
    tenor_days: int
    spot_mid: str
    forward_mid: str
    forward_bid: str
    forward_ask: str
    forward_points: str
    domestic_rate: str
    foreign_rate: str
    timestamp: str


class ForwardExecuteRequest(BaseModel):
    base_currency: str
    quote_currency: str
    direction: str  # "buy" or "sell"
    notional: Decimal
    tenor_days: int


class ForwardExecutionResponse(BaseModel):
    execution_id: str
    base_currency: str
    quote_currency: str
    direction: str
    notional: str
    contract_rate: str
    spot_at_inception: str
    tenor_days: int
    trade_date: str
    maturity_date: str
    counterparty: str
    executed_at: str


class InterpolatedRateResponse(BaseModel):
    currency: str
    tenor_days: int
    rate: float
    discount_factor: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_curves(request: Request) -> YieldCurveSimulator:
    curves = getattr(request.app.state, "yield_curve_simulator", None)
    if curves is None:
        raise HTTPException(503, "Yield curve simulator not initialized")
    return curves


def _get_fx_service(request: Request) -> FXForwardService:
    svc = getattr(request.app.state, "fx_forward_service", None)
    if svc is None:
        raise HTTPException(503, "FX forward service not initialized")
    return svc


# ---------------------------------------------------------------------------
# Yield curve endpoints
# ---------------------------------------------------------------------------


@router.get("/yield-curves", response_model=list[YieldCurveResponse])
async def get_all_curves(request: Request) -> list[YieldCurveResponse]:
    """Get current yield curves for all currencies."""
    curves = _get_curves(request)
    snapshots = curves.get_all_snapshots()
    return [
        YieldCurveResponse(
            currency=snap.currency,
            points=[
                CurvePointResponse(
                    tenor_days=p.tenor_days,
                    tenor_label=p.tenor_label,
                    rate=round(p.rate, 6),
                )
                for p in snap.points
            ],
            timestamp=snap.timestamp.isoformat(),
        )
        for snap in snapshots.values()
    ]


@router.get("/yield-curves/{currency}", response_model=YieldCurveResponse)
async def get_curve(request: Request, currency: str) -> YieldCurveResponse:
    """Get current yield curve for a specific currency."""
    curves = _get_curves(request)
    snap = curves.get_snapshot(currency.upper())
    if snap is None:
        raise HTTPException(404, f"No yield curve for {currency}")
    return YieldCurveResponse(
        currency=snap.currency,
        points=[
            CurvePointResponse(
                tenor_days=p.tenor_days,
                tenor_label=p.tenor_label,
                rate=round(p.rate, 6),
            )
            for p in snap.points
        ],
        timestamp=snap.timestamp.isoformat(),
    )


@router.get(
    "/yield-curves/{currency}/rate",
    response_model=InterpolatedRateResponse,
)
async def get_interpolated_rate(
    request: Request,
    currency: str,
    tenor_days: int = Query(..., ge=1, le=7200),
) -> InterpolatedRateResponse:
    """Get interpolated rate and discount factor for a specific tenor."""
    curves = _get_curves(request)
    snap = curves.get_snapshot(currency.upper())
    if snap is None:
        raise HTTPException(404, f"No yield curve for {currency}")
    return InterpolatedRateResponse(
        currency=currency.upper(),
        tenor_days=tenor_days,
        rate=round(snap.rate_at_tenor(tenor_days), 6),
        discount_factor=round(snap.discount_factor(tenor_days), 8),
    )


# ---------------------------------------------------------------------------
# FX forward endpoints
# ---------------------------------------------------------------------------


@router.get("/fx/forward-quote", response_model=ForwardQuoteResponse)
async def get_forward_quote(
    request: Request,
    base: str = Query(..., description="Base currency (e.g. USD)"),
    quote: str = Query(..., description="Quote currency (e.g. GBP)"),
    tenor_days: int = Query(30, ge=1, le=3600),
) -> ForwardQuoteResponse:
    """Get an FX forward quote using yield curves and spot rates."""
    svc = _get_fx_service(request)
    fwd = svc.quote_forward(base.upper(), quote.upper(), tenor_days)
    if fwd is None:
        raise HTTPException(
            404,
            f"Cannot quote {base}/{quote} — missing spot or curve data",
        )
    return ForwardQuoteResponse(
        base_currency=fwd.base_currency,
        quote_currency=fwd.quote_currency,
        tenor_days=fwd.tenor_days,
        spot_mid=str(fwd.spot_mid),
        forward_mid=str(fwd.forward_mid),
        forward_bid=str(fwd.forward_bid),
        forward_ask=str(fwd.forward_ask),
        forward_points=str(fwd.forward_points),
        domestic_rate=str(fwd.domestic_rate),
        foreign_rate=str(fwd.foreign_rate),
        timestamp=fwd.timestamp.isoformat(),
    )


@router.post("/fx/forwards", response_model=ForwardExecutionResponse)
async def execute_forward(
    request: Request,
    body: ForwardExecuteRequest,
) -> ForwardExecutionResponse:
    """Book an FX forward at current market rates."""
    svc = _get_fx_service(request)
    if body.direction not in ("buy", "sell"):
        raise HTTPException(400, "direction must be 'buy' or 'sell'")

    execution = svc.execute_forward(
        base_currency=body.base_currency.upper(),
        quote_currency=body.quote_currency.upper(),
        direction=body.direction,
        notional=body.notional,
        tenor_days=body.tenor_days,
    )
    if execution is None:
        raise HTTPException(
            404,
            f"Cannot execute — missing market data for "
            f"{body.base_currency}/{body.quote_currency}",
        )
    return ForwardExecutionResponse(
        execution_id=execution.execution_id,
        base_currency=execution.base_currency,
        quote_currency=execution.quote_currency,
        direction=execution.direction,
        notional=str(execution.notional),
        contract_rate=str(execution.contract_rate),
        spot_at_inception=str(execution.spot_at_inception),
        tenor_days=execution.tenor_days,
        trade_date=execution.trade_date.isoformat(),
        maturity_date=execution.maturity_date.isoformat(),
        counterparty=execution.counterparty,
        executed_at=execution.executed_at.isoformat(),
    )


@router.get("/fx/forwards", response_model=list[ForwardExecutionResponse])
async def list_forwards(request: Request) -> list[ForwardExecutionResponse]:
    """List all booked FX forwards."""
    svc = _get_fx_service(request)
    return [
        ForwardExecutionResponse(
            execution_id=e.execution_id,
            base_currency=e.base_currency,
            quote_currency=e.quote_currency,
            direction=e.direction,
            notional=str(e.notional),
            contract_rate=str(e.contract_rate),
            spot_at_inception=str(e.spot_at_inception),
            tenor_days=e.tenor_days,
            trade_date=e.trade_date.isoformat(),
            maturity_date=e.maturity_date.isoformat(),
            counterparty=e.counterparty,
            executed_at=e.executed_at.isoformat(),
        )
        for e in svc.list_executions()
    ]


@router.get(
    "/fx/forwards/{execution_id}",
    response_model=ForwardExecutionResponse,
)
async def get_forward(
    request: Request,
    execution_id: str,
) -> ForwardExecutionResponse:
    """Get a specific booked FX forward."""
    svc = _get_fx_service(request)
    e = svc.get_execution(execution_id)
    if e is None:
        raise HTTPException(404, f"Forward {execution_id} not found")
    return ForwardExecutionResponse(
        execution_id=e.execution_id,
        base_currency=e.base_currency,
        quote_currency=e.quote_currency,
        direction=e.direction,
        notional=str(e.notional),
        contract_rate=str(e.contract_rate),
        spot_at_inception=str(e.spot_at_inception),
        tenor_days=e.tenor_days,
        trade_date=e.trade_date.isoformat(),
        maturity_date=e.maturity_date.isoformat(),
        counterparty=e.counterparty,
        executed_at=e.executed_at.isoformat(),
    )
