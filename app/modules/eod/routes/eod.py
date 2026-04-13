"""FastAPI routes for EOD processing."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.eod.core.orchestrator import EODOrchestrator
from app.modules.eod.dependencies import get_eod_orchestrator, get_nav_snapshot_repo
from app.modules.eod.interfaces.run import (
    EODRunResult,
    EODRunSummary,
    EODStepName,
    EODStepResult,
    EODStepStatus,
)
from app.modules.eod.interfaces.snapshot import NAVHistoryPoint
from app.modules.eod.repositories import NAVSnapshotRepository
from app.shared.auth import Permission, require_permission
from app.shared.auth.request_context import RequestContext
from app.shared.database import get_db

router = APIRouter(prefix="/eod", tags=["eod"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class RunEODRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    business_date: date


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/run", response_model=EODRunResult)
async def trigger_eod_run(
    body: RunEODRequest,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    orchestrator: EODOrchestrator = Depends(get_eod_orchestrator),
    session: AsyncSession = Depends(get_db),
) -> EODRunResult:
    """Trigger an EOD run for the authenticated user's fund."""
    if not request_context.fund_slug:
        raise HTTPException(status_code=400, detail="Fund context required")
    return await orchestrator.run_eod(
        request_context.fund_slug,
        body.business_date,
        session=session,
    )


@router.get("/status/{business_date}", response_model=EODRunResult | None)
async def get_eod_status(
    business_date: date,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    orchestrator: EODOrchestrator = Depends(get_eod_orchestrator),
    session: AsyncSession = Depends(get_db),
) -> EODRunResult | None:
    """Get the status of the latest EOD run for a business date."""
    if not request_context.fund_slug:
        raise HTTPException(status_code=400, detail="Fund context required")
    run_repo = orchestrator._run_repo
    run = await run_repo.get_latest_run(business_date, request_context.fund_slug)
    if run is None:
        return None

    steps = await run_repo.get_steps(run.run_id)
    return EODRunResult(
        run_id=UUID(run.run_id),
        business_date=run.business_date,
        fund_slug=run.fund_slug,
        started_at=run.started_at,
        completed_at=run.completed_at,
        steps=[
            EODStepResult(
                step=EODStepName(s.step),
                status=EODStepStatus(s.status),
                started_at=s.started_at,
                completed_at=s.completed_at,
                error_message=s.error_message,
            )
            for s in steps
        ],
        is_successful=run.is_successful,
    )


@router.get("/history", response_model=list[EODRunSummary])
async def get_eod_history(
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    orchestrator: EODOrchestrator = Depends(get_eod_orchestrator),
    session: AsyncSession = Depends(get_db),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
) -> list[EODRunSummary]:
    """List past EOD runs for the fund."""
    if not request_context.fund_slug:
        raise HTTPException(status_code=400, detail="Fund context required")
    run_repo = orchestrator._run_repo
    runs = await run_repo.get_run_history(request_context.fund_slug, limit=limit, offset=offset)

    summaries = []
    for run in runs:
        steps = await run_repo.get_steps(run.run_id)
        summaries.append(
            EODRunSummary(
                run_id=UUID(run.run_id),
                business_date=run.business_date,
                fund_slug=run.fund_slug,
                started_at=run.started_at,
                completed_at=run.completed_at,
                is_successful=run.is_successful,
                steps_completed=sum(1 for s in steps if s.status == "completed"),
                steps_total=len(steps),
            )
        )
    return summaries


_PERIOD_DAYS = {"30d": 30, "90d": 90, "1y": 365}


@router.get("/nav/history", response_model=list[NAVHistoryPoint])
async def get_nav_history(
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    nav_repo: NAVSnapshotRepository = Depends(get_nav_snapshot_repo),
    orchestrator: EODOrchestrator = Depends(get_eod_orchestrator),
    session: AsyncSession = Depends(get_db),
    period: str = Query("90d", pattern="^(30d|90d|1y)$"),
) -> list[NAVHistoryPoint]:
    """Return aggregated NAV history for the fund's portfolios."""
    if not request_context.fund_slug:
        raise HTTPException(status_code=400, detail="Fund context required")

    fund_repo = orchestrator._fund_repo
    portfolio_repo = orchestrator._portfolio_repo

    fund = await fund_repo.get_by_slug(request_context.fund_slug)
    if fund is None:
        raise HTTPException(status_code=404, detail="Fund not found")

    portfolios = await portfolio_repo.get_by_fund(fund.id)
    portfolio_ids = [p.id for p in portfolios]
    if not portfolio_ids:
        return []

    days = _PERIOD_DAYS.get(period, 90)
    since = date.today() - timedelta(days=days)

    snapshots = await nav_repo.get_history(portfolio_ids, since=since)

    # Aggregate across portfolios per date
    date_totals: dict[date, Decimal] = {}
    date_shares: dict[date, Decimal] = {}
    for snap in snapshots:
        date_totals[snap.business_date] = date_totals.get(
            snap.business_date, Decimal(0)
        ) + snap.nav
        date_shares[snap.business_date] = date_shares.get(
            snap.business_date, Decimal(0)
        ) + snap.shares_outstanding

    return [
        NAVHistoryPoint(
            business_date=d,
            nav=date_totals[d],
            nav_per_share=(
                date_totals[d] / date_shares[d] if date_shares[d] else Decimal(0)
            ),
        )
        for d in sorted(date_totals.keys())
    ]
