"""Fund administrator REST endpoints — simulates external admin provider."""

from __future__ import annotations

from fastapi import APIRouter, Request
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
