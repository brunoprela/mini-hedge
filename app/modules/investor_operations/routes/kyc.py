"""FastAPI routes for investor operations — KYC and fund terms."""

from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.investor_operations.dependencies import get_kyc_service
from app.modules.investor_operations.interfaces import (
    FundTermsSummary,
    InvestorKYCInfo,
)
from app.modules.investor_operations.services import InvestorKYCService
from app.shared.auth import Permission, require_permission
from app.shared.auth.request_context import RequestContext
from app.shared.database import get_db

router = APIRouter(prefix="/investor-operations", tags=["investor-operations"])


# ---------------------------------------------------------------------------
#  Request schemas
# ---------------------------------------------------------------------------


class CreateFundTermsRequest(BaseModel):
    share_class: str
    lock_up_months: int = 12
    notice_period_days: int = 45
    redemption_frequency: str = "quarterly"
    gate_pct: Decimal = Decimal("0.25")
    minimum_subscription: Decimal = Decimal("1000000")
    minimum_redemption: Decimal = Decimal("100000")
    dealing_day: int = -1
    payment_days: int = 30


class ScreenInvestorRequest(BaseModel):
    name: str
    entity_type: str = "individual"
    tax_jurisdiction: str | None = None


# ---------------------------------------------------------------------------
#  Fund terms endpoints
# ---------------------------------------------------------------------------


@router.get("/fund-terms", response_model=list[FundTermsSummary])
async def list_fund_terms(
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    service: InvestorKYCService = Depends(get_kyc_service),
    session: AsyncSession = Depends(get_db),
) -> list[FundTermsSummary]:
    return await service.list_fund_terms(session=session)


@router.post("/fund-terms", response_model=FundTermsSummary)
async def create_fund_terms(
    body: CreateFundTermsRequest,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: InvestorKYCService = Depends(get_kyc_service),
    session: AsyncSession = Depends(get_db),
) -> FundTermsSummary:
    return await service.upsert_fund_terms(
        share_class=body.share_class,
        lock_up_months=body.lock_up_months,
        notice_period_days=body.notice_period_days,
        redemption_frequency=body.redemption_frequency,
        gate_pct=body.gate_pct,
        minimum_subscription=body.minimum_subscription,
        minimum_redemption=body.minimum_redemption,
        dealing_day=body.dealing_day,
        payment_days=body.payment_days,
        session=session,
    )


@router.put("/fund-terms/{terms_id}", response_model=FundTermsSummary)
async def update_fund_terms(
    terms_id: str,
    body: CreateFundTermsRequest,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: InvestorKYCService = Depends(get_kyc_service),
    session: AsyncSession = Depends(get_db),
) -> FundTermsSummary:
    return await service.upsert_fund_terms(
        share_class=body.share_class,
        lock_up_months=body.lock_up_months,
        notice_period_days=body.notice_period_days,
        redemption_frequency=body.redemption_frequency,
        gate_pct=body.gate_pct,
        minimum_subscription=body.minimum_subscription,
        minimum_redemption=body.minimum_redemption,
        dealing_day=body.dealing_day,
        payment_days=body.payment_days,
        session=session,
    )


# ---------------------------------------------------------------------------
#  KYC endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/investors/{investor_id}/kyc",
    response_model=InvestorKYCInfo | None,
)
async def get_investor_kyc(
    investor_id: str,
    _ctx: RequestContext = require_permission(Permission.COMPLIANCE_READ),
    service: InvestorKYCService = Depends(get_kyc_service),
    session: AsyncSession = Depends(get_db),
) -> InvestorKYCInfo | None:
    return await service.get_investor_kyc(investor_id, session=session)


@router.post(
    "/investors/{investor_id}/kyc/screen",
    response_model=InvestorKYCInfo,
)
async def screen_investor(
    investor_id: str,
    body: ScreenInvestorRequest,
    _ctx: RequestContext = require_permission(Permission.COMPLIANCE_WRITE),
    service: InvestorKYCService = Depends(get_kyc_service),
    session: AsyncSession = Depends(get_db),
) -> InvestorKYCInfo:
    return await service.screen_investor(
        investor_id=investor_id,
        name=body.name,
        entity_type=body.entity_type,
        tax_jurisdiction=body.tax_jurisdiction,
        session=session,
    )
