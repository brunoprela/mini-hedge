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
from app.modules.fee_accounting.models.fee_schedule import FeeScheduleRecord
from app.modules.fee_accounting.repositories.fee_schedule import FeeScheduleRepository
from app.modules.fee_accounting.services import FeeAccountingService
from app.shared.database import get_db

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
    share_class: str = "default"
    management_fee_bps: int
    performance_fee_pct: Decimal
    hurdle_rate_pct: Decimal
    high_water_mark: bool = True
    crystallization_frequency: str = "quarterly"
    payment_frequency: str = "quarterly"


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
    portfolio_id: UUID = Query(...),
    start: date | None = Query(None),
    end: date | None = Query(None),
    fee_service: FeeAccountingService = Depends(get_fee_accounting_service),
    session: AsyncSession = Depends(get_db),
) -> list[FeeAccrualResponse]:
    records = await fee_service.get_accruals(portfolio_id, start=start, end=end, session=session)
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
    share_class: str = Query("default"),
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
    schedule_repo: FeeScheduleRepository = Depends(get_fee_schedule_repo),
    session: AsyncSession = Depends(get_db),
) -> list[FeeScheduleResponse]:
    records = await schedule_repo.get_all_by_fund(fund_slug, session=session)
    return [_schedule_to_response(r) for r in records]


@router.put("/schedule", response_model=FeeScheduleResponse)
async def update_fee_schedule(
    fund_slug: str,
    body: FeeScheduleUpdate,
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
