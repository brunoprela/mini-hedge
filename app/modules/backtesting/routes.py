"""FastAPI routes for backtesting."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from app.modules.backtesting.dependencies import get_backtesting_service
from app.modules.backtesting.interface import (
    BacktestConfig,
    BacktestResult,
    BacktestSummary,
    BacktestTrade,
    EquityCurvePoint,
)
from app.modules.backtesting.tear_sheet import TearSheet
from app.shared.auth import Permission, require_permission
from app.shared.database import get_db, get_read_db

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.backtesting.service import BacktestingService
    from app.shared.request_context import RequestContext

router = APIRouter(prefix="/backtesting", tags=["backtesting"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class PricePoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    date: str  # ISO date
    price: Decimal


class RunBacktestRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    config: BacktestConfig
    signal_name: str = "equal_weight"
    price_data: dict[str, list[PricePoint]]


class CompareRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    backtest_ids: list[str]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/run", response_model=BacktestSummary)
async def run_backtest(
    body: RunBacktestRequest,
    request_context: RequestContext = require_permission(Permission.RISK_WRITE),
    service: BacktestingService = Depends(get_backtesting_service),
    session: AsyncSession = Depends(get_db),
) -> BacktestSummary:
    """Submit and run a backtest."""
    from datetime import date as date_type

    # Convert price_data from request format to engine format
    price_data: dict[str, list[tuple[date_type, Decimal]]] = {}
    for inst_id, points in body.price_data.items():
        price_data[inst_id] = [
            (date_type.fromisoformat(p.date), p.price) for p in points
        ]

    return await service.submit_backtest(
        body.config,
        price_data,
        body.signal_name,
        session=session,
    )


@router.get("/", response_model=list[BacktestSummary])
async def list_backtests(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: BacktestingService = Depends(get_backtesting_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[BacktestSummary]:
    """List backtests, optionally filtered by status."""
    return await service.list_backtests(
        status=status, limit=limit, session=session,
    )


@router.get("/{backtest_id}", response_model=BacktestResult)
async def get_backtest(
    backtest_id: str,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: BacktestingService = Depends(get_backtesting_service),
    session: AsyncSession = Depends(get_read_db),
) -> BacktestResult:
    """Get full backtest result."""
    result = await service.get_backtest(backtest_id, session=session)
    if result is None:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return result


@router.get(
    "/{backtest_id}/equity-curve",
    response_model=list[EquityCurvePoint],
)
async def get_equity_curve(
    backtest_id: str,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: BacktestingService = Depends(get_backtesting_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[EquityCurvePoint]:
    """Get just the equity curve for a backtest."""
    result = await service.get_backtest(backtest_id, session=session)
    if result is None:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return result.equity_curve


@router.get(
    "/{backtest_id}/tear-sheet",
    response_model=TearSheet,
)
async def get_tear_sheet(
    backtest_id: str,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: BacktestingService = Depends(get_backtesting_service),
    session: AsyncSession = Depends(get_read_db),
) -> TearSheet:
    """Generate a comprehensive quantitative tear sheet for a backtest."""
    tear_sheet = await service.get_tear_sheet(backtest_id, session=session)
    if tear_sheet is None:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return tear_sheet


@router.get(
    "/{backtest_id}/trades",
    response_model=list[BacktestTrade],
)
async def get_trades(
    backtest_id: str,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: BacktestingService = Depends(get_backtesting_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[BacktestTrade]:
    """Get just the trades for a backtest."""
    result = await service.get_backtest(backtest_id, session=session)
    if result is None:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return result.trades


@router.delete("/{backtest_id}", status_code=204)
async def delete_backtest(
    backtest_id: str,
    request_context: RequestContext = require_permission(Permission.RISK_WRITE),
    service: BacktestingService = Depends(get_backtesting_service),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a backtest."""
    await service.delete_backtest(backtest_id, session=session)


@router.post("/compare", response_model=list[BacktestSummary])
async def compare_backtests(
    body: CompareRequest,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: BacktestingService = Depends(get_backtesting_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[BacktestSummary]:
    """Compare multiple backtests side by side."""
    return await service.compare_backtests(
        body.backtest_ids, session=session,
    )
