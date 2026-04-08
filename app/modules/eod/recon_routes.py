"""FastAPI routes for reconciliation results and break management."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from app.modules.eod.dependencies import get_break_repo, get_escalation_policy, get_recon_repo
from app.modules.eod.interface import (
    AgingSummary,
    AutoResolutionResult,
    BreakStatus,
    BreakType,
    SLAStatus,
    TrackedBreak,
)
from app.shared.auth import Permission, require_permission
from app.shared.database import get_db

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.eod.escalation import EscalationPolicy
    from app.modules.eod.repository import (
        ReconciliationBreakRepository,
        ReconciliationRepository,
    )
    from app.shared.request_context import RequestContext

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


class UpdateBreakRequest(BaseModel):
    status: BreakStatus
    assigned_to: str | None = None
    resolution_note: str | None = None


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
    record = await recon_repo.get_by_date(
        str(portfolio_id), business_date, session=session
    )
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


# ---------------------------------------------------------------------------
# Routes — Break Management
# ---------------------------------------------------------------------------


@router.get(
    "/portfolios/{portfolio_id}/breaks",
    response_model=list[TrackedBreak],
)
async def list_breaks(
    portfolio_id: UUID,
    business_date: date | None = Query(None),
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    break_repo: ReconciliationBreakRepository = Depends(get_break_repo),
    session: AsyncSession = Depends(get_db),
) -> list[TrackedBreak]:
    """List breaks for a portfolio — by date or all open breaks."""
    if business_date:
        records = await break_repo.list_by_portfolio_date(
            str(portfolio_id), business_date, session=session
        )
    else:
        records = await break_repo.list_open(str(portfolio_id), session=session)

    return [_to_tracked_break(r) for r in records]


@router.get("/breaks/{break_id}", response_model=TrackedBreak)
async def get_break(
    break_id: UUID,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    break_repo: ReconciliationBreakRepository = Depends(get_break_repo),
    session: AsyncSession = Depends(get_db),
) -> TrackedBreak:
    """Get a single break by ID."""
    record = await break_repo.get_by_id(str(break_id), session=session)
    if record is None:
        raise HTTPException(status_code=404, detail="Break not found")
    return _to_tracked_break(record)


@router.patch("/breaks/{break_id}", response_model=TrackedBreak)
async def update_break(
    break_id: UUID,
    body: UpdateBreakRequest,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    break_repo: ReconciliationBreakRepository = Depends(get_break_repo),
    session: AsyncSession = Depends(get_db),
) -> TrackedBreak:
    """Update break status (investigate, resolve, escalate)."""
    resolved_at = (
        datetime.now(UTC) if body.status == BreakStatus.RESOLVED else None
    )
    record = await break_repo.update_status(
        str(break_id),
        status=body.status.value,
        assigned_to=body.assigned_to,
        resolution_note=body.resolution_note,
        resolved_at=resolved_at,
        session=session,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Break not found")
    return _to_tracked_break(record)


# ---------------------------------------------------------------------------
# Routes — Auto-Resolution & Escalation
# ---------------------------------------------------------------------------


class BreakWithSLA(BaseModel):
    model_config = ConfigDict(frozen=True)

    tracked_break: TrackedBreak
    sla_status: SLAStatus


@router.post(
    "/portfolios/{portfolio_id}/auto-resolve",
    response_model=AutoResolutionResult,
)
async def auto_resolve_breaks(
    portfolio_id: UUID,
    business_date: date = Query(default_factory=date.today),
    request_context: RequestContext = require_permission(Permission.RISK_WRITE),
    break_repo: ReconciliationBreakRepository = Depends(get_break_repo),
    session: AsyncSession = Depends(get_db),
) -> AutoResolutionResult:
    """Run auto-resolution rules against open breaks for a portfolio."""
    from app.modules.eod.auto_resolver import BreakAutoResolver, default_rules

    resolver = BreakAutoResolver(default_rules(), break_repo)
    return await resolver.process_breaks(
        str(portfolio_id), business_date, session=session
    )


@router.get(
    "/portfolios/{portfolio_id}/aging",
    response_model=AgingSummary,
)
async def get_aging_summary(
    portfolio_id: UUID,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    break_repo: ReconciliationBreakRepository = Depends(get_break_repo),
    escalation_policy: EscalationPolicy = Depends(get_escalation_policy),
    session: AsyncSession = Depends(get_db),
) -> AgingSummary:
    """Return aging summary for open breaks in a portfolio."""
    open_breaks = await break_repo.list_open(str(portfolio_id), session=session)
    return escalation_policy.get_aging_summary(open_breaks)


@router.get(
    "/portfolios/{portfolio_id}/sla-status",
    response_model=list[BreakWithSLA],
)
async def get_sla_status(
    portfolio_id: UUID,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    break_repo: ReconciliationBreakRepository = Depends(get_break_repo),
    escalation_policy: EscalationPolicy = Depends(get_escalation_policy),
    session: AsyncSession = Depends(get_db),
) -> list[BreakWithSLA]:
    """Return all open breaks with their SLA status."""
    open_breaks = await break_repo.list_open(str(portfolio_id), session=session)
    return [
        BreakWithSLA(
            tracked_break=_to_tracked_break(brk),
            sla_status=escalation_policy.check_sla(brk),
        )
        for brk in open_breaks
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_tracked_break(record: object) -> TrackedBreak:
    from app.modules.eod.models import ReconciliationBreakRecord

    assert isinstance(record, ReconciliationBreakRecord)
    return TrackedBreak(
        id=UUID(record.id),
        portfolio_id=UUID(record.portfolio_id),
        business_date=record.business_date,
        instrument_id=record.instrument_id,
        break_type=BreakType(record.break_type),
        internal_quantity=record.internal_quantity,
        broker_quantity=record.broker_quantity,
        admin_quantity=record.admin_quantity,
        difference=record.difference,
        is_material=record.is_material,
        currency=record.currency,
        internal_balance=record.internal_balance,
        admin_balance=record.admin_balance,
        status=BreakStatus(record.status),
        assigned_to=record.assigned_to,
        resolution_note=record.resolution_note,
        created_at=record.created_at,
        resolved_at=record.resolved_at,
    )
