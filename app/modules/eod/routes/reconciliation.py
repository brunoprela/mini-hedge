"""FastAPI routes for reconciliation results."""

from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.eod.dependencies import get_recon_repo
from app.modules.eod.repositories import ReconciliationRepository
from app.shared.auth import Permission, require_permission
from app.shared.auth.request_context import RequestContext
from app.shared.database import get_db

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ReconSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio_id: UUID
    business_date: date
    total_positions: int
    matched_positions: int
    is_clean: bool
    break_count: int
    reconciled_at: datetime


# ---------------------------------------------------------------------------
# Routes — Reconciliation Results
# ---------------------------------------------------------------------------


@router.get(
    "/portfolios/{portfolio_id}/latest",
    response_model=ReconSummary | None,
)
async def get_latest_recon(
    portfolio_id: UUID,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    recon_repo: ReconciliationRepository = Depends(get_recon_repo),
    session: AsyncSession = Depends(get_db),
) -> ReconSummary | None:
    """Get the latest reconciliation result for a portfolio."""
    record = await recon_repo.get_latest(str(portfolio_id), session=session)
    if record is None:
        return None
    breaks_list = record.breaks if isinstance(record.breaks, list) else []
    return ReconSummary(
        portfolio_id=UUID(record.portfolio_id),
        business_date=record.business_date,
        total_positions=record.total_positions,
        matched_positions=record.matched_positions,
        is_clean=record.is_clean,
        break_count=len(breaks_list),
        reconciled_at=record.reconciled_at,
    )


@router.get(
    "/portfolios/{portfolio_id}/history",
    response_model=list[ReconSummary],
)
async def get_recon_history(
    portfolio_id: UUID,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    recon_repo: ReconciliationRepository = Depends(get_recon_repo),
    session: AsyncSession = Depends(get_db),
    limit: int = Query(30, le=100),
    offset: int = Query(0, ge=0),
) -> list[ReconSummary]:
    """List reconciliation history for a portfolio."""
    records = await recon_repo.list_by_portfolio(
        str(portfolio_id), limit=limit, offset=offset, session=session
    )
    results = []
    for r in records:
        breaks_list = r.breaks if isinstance(r.breaks, list) else []
        results.append(
            ReconSummary(
                portfolio_id=UUID(r.portfolio_id),
                business_date=r.business_date,
                total_positions=r.total_positions,
                matched_positions=r.matched_positions,
                is_clean=r.is_clean,
                break_count=len(breaks_list),
                reconciled_at=r.reconciled_at,
            )
        )
    return results


@router.get(
    "/portfolios/{portfolio_id}/date/{business_date}",
    response_model=ReconSummary | None,
)
async def get_recon_by_date(
    portfolio_id: UUID,
    business_date: date,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    recon_repo: ReconciliationRepository = Depends(get_recon_repo),
    session: AsyncSession = Depends(get_db),
) -> ReconSummary | None:
    """Get reconciliation result for a specific date."""
    record = await recon_repo.get_by_date(str(portfolio_id), business_date, session=session)
    if record is None:
        return None
    breaks_list = record.breaks if isinstance(record.breaks, list) else []
    return ReconSummary(
        portfolio_id=UUID(record.portfolio_id),
        business_date=record.business_date,
        total_positions=record.total_positions,
        matched_positions=record.matched_positions,
        is_clean=record.is_clean,
        break_count=len(breaks_list),
        reconciled_at=record.reconciled_at,
    )
