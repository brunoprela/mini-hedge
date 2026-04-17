"""FastAPI routes for the fee accounting module."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.fee_accounting.dependencies import (
    get_fee_accounting_service,
    get_fee_schedule_repo,
)
from app.modules.fee_accounting.interfaces import AccrualStatus, FeeType
from app.modules.fee_accounting.models.fee_accrual import FeeAccrualRecord
from app.modules.fee_accounting.models.fee_schedule import FeeScheduleRecord
from app.modules.fee_accounting.repositories.fee_schedule import FeeScheduleRepository
from app.modules.fee_accounting.services import FeeAccountingService
from app.modules.platform.dependencies import get_fund_repo, get_portfolio_repo
from app.modules.platform.repositories import FundRepository, PortfolioRepository
from app.shared.auth import Permission, require_permission
from app.shared.auth.request_context import RequestContext
from app.shared.database import get_db

_DEFAULT_SHARE_CLASS = "default"
_DEFAULT_CRYSTALLIZATION_FREQUENCY = "quarterly"

router = APIRouter(prefix="/funds/{fund_slug}/fees", tags=["fees"])


# ---- Request / Response schemas ----


class FeeScheduleResponse(BaseModel):
    fund_slug: str
    share_class: str
    management_fee_bps: int
    performance_fee_pct: Decimal
    hurdle_rate_pct: Decimal
    high_water_mark: bool
    crystallization_frequency: str
    payment_frequency: str


class FeeScheduleUpdate(BaseModel):
    share_class: str = _DEFAULT_SHARE_CLASS
    management_fee_bps: int
    performance_fee_pct: Decimal
    hurdle_rate_pct: Decimal
    high_water_mark: bool = True
    crystallization_frequency: str = _DEFAULT_CRYSTALLIZATION_FREQUENCY
    payment_frequency: str = _DEFAULT_CRYSTALLIZATION_FREQUENCY


class FeeAccrualResponse(BaseModel):
    id: UUID | None = None
    portfolio_id: UUID
    fee_type: FeeType
    accrual_date: date
    nav_basis: Decimal
    accrued_amount: Decimal
    cumulative_amount: Decimal
    status: AccrualStatus
    created_at: str | None = None


# ---- Endpoints ----


@router.get("/accruals", response_model=list[FeeAccrualResponse])
async def list_accruals(
    fund_slug: str,
    portfolio_id: UUID | None = Query(None),
    start: date | None = Query(None),
    end: date | None = Query(None),
    request_context: RequestContext = require_permission(Permission.CAPITAL_READ),
    fee_service: FeeAccountingService = Depends(get_fee_accounting_service),
    fund_repo: FundRepository = Depends(get_fund_repo),
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repo),
    session: AsyncSession = Depends(get_db),
) -> list[FeeAccrualResponse]:
    if portfolio_id is None:
        fund = await fund_repo.get_by_slug(fund_slug, session=session)
        if fund is None:
            raise HTTPException(status_code=404, detail="Fund not found")
        portfolios = await portfolio_repo.get_by_fund(fund.id, session=session)
        records = await fee_service.get_accruals_for_fund(
            [UUID(p.id) for p in portfolios], start=start, end=end, session=session
        )
    else:
        records = await fee_service.get_accruals(
            portfolio_id, start=start, end=end, session=session
        )
    return [
        FeeAccrualResponse(
            id=UUID(r.id) if r.id else None,
            portfolio_id=UUID(r.portfolio_id),
            fee_type=FeeType(r.fee_type),
            accrual_date=r.accrual_date,
            nav_basis=r.nav_basis,
            accrued_amount=r.accrued_amount,
            cumulative_amount=r.cumulative_amount,
            status=AccrualStatus(r.status),
            created_at=str(r.created_at) if r.created_at else None,
        )
        for r in records
    ]


@router.get("/schedule", response_model=FeeScheduleResponse)
async def get_fee_schedule(
    fund_slug: str,
    share_class: str = Query(_DEFAULT_SHARE_CLASS),
    request_context: RequestContext = require_permission(Permission.CAPITAL_READ),
    schedule_repo: FeeScheduleRepository = Depends(get_fee_schedule_repo),
    session: AsyncSession = Depends(get_db),
) -> FeeScheduleResponse:
    record = await schedule_repo.get_by_fund_slug(
        fund_slug,
        share_class=share_class,
        session=session,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Fee schedule not found")
    return _schedule_to_response(record)


@router.get("/schedules", response_model=list[FeeScheduleResponse])
async def list_fee_schedules(
    fund_slug: str,
    request_context: RequestContext = require_permission(Permission.CAPITAL_READ),
    schedule_repo: FeeScheduleRepository = Depends(get_fee_schedule_repo),
    session: AsyncSession = Depends(get_db),
) -> list[FeeScheduleResponse]:
    records = await schedule_repo.list_by_fund(fund_slug, session=session)
    return [_schedule_to_response(r) for r in records]


@router.put("/schedule", response_model=FeeScheduleResponse)
async def update_fee_schedule(
    fund_slug: str,
    body: FeeScheduleUpdate,
    request_context: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    schedule_repo: FeeScheduleRepository = Depends(get_fee_schedule_repo),
    session: AsyncSession = Depends(get_db),
) -> FeeScheduleResponse:
    record = FeeScheduleRecord(
        fund_slug=fund_slug,
        share_class=body.share_class,
        management_fee_bps=body.management_fee_bps,
        performance_fee_pct=body.performance_fee_pct,
        hurdle_rate_pct=body.hurdle_rate_pct,
        high_water_mark=body.high_water_mark,
        crystallization_frequency=body.crystallization_frequency,
        payment_frequency=body.payment_frequency,
    )
    saved = await schedule_repo.upsert(record, session=session)
    return _schedule_to_response(saved)


class FeeSummaryResponse(BaseModel):
    portfolio_id: UUID | None = None
    totals: dict[str, Decimal]


class AccrualTriggerRequest(BaseModel):
    portfolio_id: UUID | None = None
    nav: Decimal | None = None
    business_date: date
    share_class: str = _DEFAULT_SHARE_CLASS


class CrystallizationTriggerRequest(BaseModel):
    portfolio_id: UUID | None = None
    business_date: date
    share_class: str = _DEFAULT_SHARE_CLASS


class ApproveAccrualsRequest(BaseModel):
    accrual_ids: list[UUID]


@router.get("/summary", response_model=FeeSummaryResponse)
async def get_fee_summary(
    fund_slug: str,
    portfolio_id: UUID | None = Query(None),
    request_context: RequestContext = require_permission(Permission.CAPITAL_READ),
    fee_service: FeeAccountingService = Depends(get_fee_accounting_service),
    fund_repo: FundRepository = Depends(get_fund_repo),
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repo),
    session: AsyncSession = Depends(get_db),
) -> FeeSummaryResponse:
    if portfolio_id is None:
        fund = await fund_repo.get_by_slug(fund_slug, session=session)
        if fund is None:
            raise HTTPException(status_code=404, detail="Fund not found")
        portfolios = await portfolio_repo.get_by_fund(fund.id, session=session)
        totals = await fee_service.get_fund_summary(
            [UUID(p.id) for p in portfolios], session=session
        )
        return FeeSummaryResponse(portfolio_id=None, totals=totals)
    totals = await fee_service.get_fee_summary(portfolio_id, session=session)
    return FeeSummaryResponse(portfolio_id=portfolio_id, totals=totals)


@router.post("/accrue-daily", response_model=list[FeeAccrualResponse], status_code=201)
async def trigger_daily_accrual(
    fund_slug: str,
    body: AccrualTriggerRequest,
    request_context: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    fee_service: FeeAccountingService = Depends(get_fee_accounting_service),
    fund_repo: FundRepository = Depends(get_fund_repo),
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repo),
    session: AsyncSession = Depends(get_db),
) -> list[FeeAccrualResponse]:
    if body.portfolio_id is None:
        fund = await fund_repo.get_by_slug(fund_slug, session=session)
        if fund is None:
            raise HTTPException(status_code=404, detail="Fund not found")
        portfolios = await portfolio_repo.get_by_fund(fund.id, session=session)
        all_records: list[FeeAccrualRecord] = []
        for portfolio in portfolios:
            nav = body.nav if body.nav is not None else Decimal(0)
            records = await fee_service.accrue_daily_fees(
                UUID(portfolio.id),
                fund_slug,
                nav,
                body.business_date,
                share_class=body.share_class,
                session=session,
            )
            all_records.extend(records)
        return [
            FeeAccrualResponse(
                id=UUID(r.id) if r.id else None,
                portfolio_id=UUID(r.portfolio_id),
                fee_type=FeeType(r.fee_type),
                accrual_date=r.accrual_date,
                nav_basis=r.nav_basis,
                accrued_amount=r.accrued_amount,
                cumulative_amount=r.cumulative_amount,
                status=AccrualStatus(r.status),
                created_at=str(r.created_at) if r.created_at else None,
            )
            for r in all_records
        ]
    if body.nav is None:
        raise HTTPException(status_code=400, detail="nav is required when portfolio_id is provided")
    records = await fee_service.accrue_daily_fees(
        body.portfolio_id,
        fund_slug,
        body.nav,
        body.business_date,
        share_class=body.share_class,
        session=session,
    )
    return [
        FeeAccrualResponse(
            id=UUID(r.id) if r.id else None,
            portfolio_id=UUID(r.portfolio_id),
            fee_type=FeeType(r.fee_type),
            accrual_date=r.accrual_date,
            nav_basis=r.nav_basis,
            accrued_amount=r.accrued_amount,
            cumulative_amount=r.cumulative_amount,
            status=AccrualStatus(r.status),
            created_at=str(r.created_at) if r.created_at else None,
        )
        for r in records
    ]


@router.post("/crystallize", status_code=204)
async def trigger_crystallization(
    fund_slug: str,
    body: CrystallizationTriggerRequest,
    request_context: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    fee_service: FeeAccountingService = Depends(get_fee_accounting_service),
    fund_repo: FundRepository = Depends(get_fund_repo),
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repo),
    session: AsyncSession = Depends(get_db),
) -> None:
    if body.portfolio_id is None:
        fund = await fund_repo.get_by_slug(fund_slug, session=session)
        if fund is None:
            raise HTTPException(status_code=404, detail="Fund not found")
        portfolios = await portfolio_repo.get_by_fund(fund.id, session=session)
        for portfolio in portfolios:
            await fee_service.crystallize_fees(
                UUID(portfolio.id),
                fund_slug,
                body.business_date,
                share_class=body.share_class,
                session=session,
            )
        return None
    await fee_service.crystallize_fees(
        body.portfolio_id,
        fund_slug,
        body.business_date,
        share_class=body.share_class,
        session=session,
    )


class ApproveAccrualsResponse(BaseModel):
    approved: int


@router.post("/approve", response_model=ApproveAccrualsResponse)
async def approve_accruals(
    fund_slug: str,
    body: ApproveAccrualsRequest,
    request_context: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    fee_service: FeeAccountingService = Depends(get_fee_accounting_service),
    session: AsyncSession = Depends(get_db),
) -> ApproveAccrualsResponse:
    """Approve (crystallize) a batch of pending fee accruals.

    Delegates to ``FeeAccountingService.approve_accruals`` so state-transition
    validation, audit events, and notifications run consistently with the
    rest of the fee lifecycle.
    """
    count = await fee_service.approve_accruals(
        body.accrual_ids,
        actor_id=request_context.actor_id,
        fund_slug=fund_slug,
        session=session,
    )
    return ApproveAccrualsResponse(approved=count)


def _schedule_to_response(record: FeeScheduleRecord) -> FeeScheduleResponse:
    return FeeScheduleResponse(
        fund_slug=record.fund_slug,
        share_class=record.share_class,
        management_fee_bps=record.management_fee_bps,
        performance_fee_pct=record.performance_fee_pct,
        hurdle_rate_pct=record.hurdle_rate_pct,
        high_water_mark=record.high_water_mark,
        crystallization_frequency=record.crystallization_frequency,
        payment_frequency=record.payment_frequency,
    )
