"""FastAPI routes for EOD processing."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.eod.dependencies import get_eod_orchestrator
from app.modules.eod.interface import (
    EODRunResult,
    EODRunSummary,
    EODStepName,
    EODStepResult,
    EODStepStatus,
)
from app.modules.eod.orchestrator import EODOrchestrator
from app.shared.auth import Permission, require_permission
from app.shared.database import get_db
from app.shared.request_context import RequestContext

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
