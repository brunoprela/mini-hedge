"""FastAPI routes for investor operations — subscription/redemption workflows."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.modules.investor_operations.dependencies import get_investor_ops_service
from app.modules.investor_operations.interface import (
    FundTermsSummary,
    GateCheckResult,
    InvestorKYCInfo,
    QueueSummary,
    RedemptionRequestSummary,
    SubscriptionRequestSummary,
)
from app.shared.auth import Permission, require_permission
from app.shared.database import get_db

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.investor_operations.service import InvestorOperationsService
    from app.shared.auth.request_context import RequestContext

router = APIRouter(prefix="/investor-operations", tags=["investor-operations"])


# ---------------------------------------------------------------------------
#  Request schemas
# ---------------------------------------------------------------------------


class SubmitSubscriptionRequest(BaseModel):
    investor_id: str
    amount: Decimal
    share_class: str = "default"


class KYCDecisionRequest(BaseModel):
    approved: bool
    decision_by: str
    notes: str = ""


class OpsReviewRequest(BaseModel):
    approved: bool
    decision_by: str
    notes: str = ""


class GPDecisionRequest(BaseModel):
    approved: bool
    decision_by: str


class ConfirmWireRequest(BaseModel):
    wire_reference: str


class CancelRequest(BaseModel):
    reason: str
    cancelled_by: str


class SubmitRedemptionRequest(BaseModel):
    investor_id: str
    amount: Decimal
    notice_date: date | None = None


class ValidateRedemptionRequest(BaseModel):
    share_class: str = "default"
    subscription_date: date | None = None


class GateCheckRequest(BaseModel):
    dealing_date: date
    fund_nav: Decimal
    gate_pct: Decimal | None = None
    share_class: str = "default"


class ExecuteRequest(BaseModel):
    dealing_date: date
    nav_per_share: Decimal
    portfolio_id: UUID


class ConfirmPaymentRequest(BaseModel):
    payment_reference: str


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
#  Subscription endpoints
# ---------------------------------------------------------------------------


@router.post("/subscriptions", response_model=SubscriptionRequestSummary)
async def submit_subscription(
    body: SubmitSubscriptionRequest,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: InvestorOperationsService = Depends(get_investor_ops_service),
    session: AsyncSession = Depends(get_db),
) -> SubscriptionRequestSummary:
    return await service.submit_subscription(
        investor_id=body.investor_id,
        amount=body.amount,
        share_class=body.share_class,
        session=session,
    )


@router.get("/subscriptions", response_model=list[SubscriptionRequestSummary])
async def list_subscriptions(
    state: str | None = None,
    investor_id: str | None = None,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    service: InvestorOperationsService = Depends(get_investor_ops_service),
    session: AsyncSession = Depends(get_db),
) -> list[SubscriptionRequestSummary]:
    return await service.list_subscriptions(state=state, investor_id=investor_id, session=session)


@router.get(
    "/subscriptions/{request_id}",
    response_model=SubscriptionRequestSummary,
)
async def get_subscription(
    request_id: str,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    service: InvestorOperationsService = Depends(get_investor_ops_service),
    session: AsyncSession = Depends(get_db),
) -> SubscriptionRequestSummary:
    result = await service.get_subscription(request_id, session=session)
    if result is None:
        raise HTTPException(404, f"Subscription {request_id} not found")
    return result


@router.post(
    "/subscriptions/{request_id}/kyc-decision",
    response_model=SubscriptionRequestSummary,
)
async def kyc_decision(
    request_id: str,
    body: KYCDecisionRequest,
    _ctx: RequestContext = require_permission(Permission.COMPLIANCE_WRITE),
    service: InvestorOperationsService = Depends(get_investor_ops_service),
    session: AsyncSession = Depends(get_db),
) -> SubscriptionRequestSummary:
    return await service.record_kyc_decision(
        request_id,
        approved=body.approved,
        decision_by=body.decision_by,
        notes=body.notes,
        session=session,
    )


@router.post(
    "/subscriptions/{request_id}/ops-review",
    response_model=SubscriptionRequestSummary,
)
async def ops_review(
    request_id: str,
    body: OpsReviewRequest,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: InvestorOperationsService = Depends(get_investor_ops_service),
    session: AsyncSession = Depends(get_db),
) -> SubscriptionRequestSummary:
    return await service.ops_review(
        request_id,
        approved=body.approved,
        decision_by=body.decision_by,
        notes=body.notes,
        session=session,
    )


@router.post(
    "/subscriptions/{request_id}/gp-decision",
    response_model=SubscriptionRequestSummary,
)
async def gp_decision(
    request_id: str,
    body: GPDecisionRequest,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: InvestorOperationsService = Depends(get_investor_ops_service),
    session: AsyncSession = Depends(get_db),
) -> SubscriptionRequestSummary:
    return await service.gp_decision(
        request_id,
        approved=body.approved,
        decision_by=body.decision_by,
        session=session,
    )


@router.post(
    "/subscriptions/{request_id}/confirm-wire",
    response_model=SubscriptionRequestSummary,
)
async def confirm_wire(
    request_id: str,
    body: ConfirmWireRequest,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: InvestorOperationsService = Depends(get_investor_ops_service),
    session: AsyncSession = Depends(get_db),
) -> SubscriptionRequestSummary:
    return await service.confirm_wire(
        request_id, wire_reference=body.wire_reference, session=session
    )


@router.post(
    "/subscriptions/{request_id}/cancel",
    response_model=SubscriptionRequestSummary,
)
async def cancel_subscription(
    request_id: str,
    body: CancelRequest,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: InvestorOperationsService = Depends(get_investor_ops_service),
    session: AsyncSession = Depends(get_db),
) -> SubscriptionRequestSummary:
    return await service.cancel_subscription(
        request_id,
        reason=body.reason,
        cancelled_by=body.cancelled_by,
        session=session,
    )


@router.post(
    "/subscriptions/execute",
    response_model=list[SubscriptionRequestSummary],
)
async def execute_subscriptions(
    body: ExecuteRequest,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: InvestorOperationsService = Depends(get_investor_ops_service),
    session: AsyncSession = Depends(get_db),
) -> list[SubscriptionRequestSummary]:
    return await service.execute_subscriptions(
        dealing_date=body.dealing_date,
        nav_per_share=body.nav_per_share,
        portfolio_id=body.portfolio_id,
        session=session,
    )


# ---------------------------------------------------------------------------
#  Redemption endpoints
# ---------------------------------------------------------------------------


@router.post("/redemptions", response_model=RedemptionRequestSummary)
async def submit_redemption(
    body: SubmitRedemptionRequest,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: InvestorOperationsService = Depends(get_investor_ops_service),
    session: AsyncSession = Depends(get_db),
) -> RedemptionRequestSummary:
    return await service.submit_redemption(
        investor_id=body.investor_id,
        amount=body.amount,
        notice_date=body.notice_date,
        session=session,
    )


@router.get("/redemptions", response_model=list[RedemptionRequestSummary])
async def list_redemptions(
    state: str | None = None,
    investor_id: str | None = None,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    service: InvestorOperationsService = Depends(get_investor_ops_service),
    session: AsyncSession = Depends(get_db),
) -> list[RedemptionRequestSummary]:
    return await service.list_redemptions(state=state, investor_id=investor_id, session=session)


@router.get(
    "/redemptions/{request_id}",
    response_model=RedemptionRequestSummary,
)
async def get_redemption(
    request_id: str,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    service: InvestorOperationsService = Depends(get_investor_ops_service),
    session: AsyncSession = Depends(get_db),
) -> RedemptionRequestSummary:
    result = await service.get_redemption(request_id, session=session)
    if result is None:
        raise HTTPException(404, f"Redemption {request_id} not found")
    return result


@router.post(
    "/redemptions/{request_id}/validate",
    response_model=RedemptionRequestSummary,
)
async def validate_redemption(
    request_id: str,
    body: ValidateRedemptionRequest,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: InvestorOperationsService = Depends(get_investor_ops_service),
    session: AsyncSession = Depends(get_db),
) -> RedemptionRequestSummary:
    return await service.validate_redemption(
        request_id,
        share_class=body.share_class,
        subscription_date=body.subscription_date,
        session=session,
    )


@router.post("/redemptions/gate-check", response_model=GateCheckResult)
async def run_gate_check(
    body: GateCheckRequest,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: InvestorOperationsService = Depends(get_investor_ops_service),
    session: AsyncSession = Depends(get_db),
) -> GateCheckResult:
    return await service.run_gate_check(
        dealing_date=body.dealing_date,
        fund_nav=body.fund_nav,
        gate_pct=body.gate_pct,
        share_class=body.share_class,
        session=session,
    )


@router.post(
    "/redemptions/execute",
    response_model=list[RedemptionRequestSummary],
)
async def execute_redemptions(
    body: ExecuteRequest,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: InvestorOperationsService = Depends(get_investor_ops_service),
    session: AsyncSession = Depends(get_db),
) -> list[RedemptionRequestSummary]:
    return await service.execute_redemptions(
        dealing_date=body.dealing_date,
        nav_per_share=body.nav_per_share,
        portfolio_id=body.portfolio_id,
        session=session,
    )


@router.post(
    "/redemptions/{request_id}/confirm-payment",
    response_model=RedemptionRequestSummary,
)
async def confirm_payment(
    request_id: str,
    body: ConfirmPaymentRequest,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: InvestorOperationsService = Depends(get_investor_ops_service),
    session: AsyncSession = Depends(get_db),
) -> RedemptionRequestSummary:
    return await service.confirm_payment(
        request_id,
        payment_reference=body.payment_reference,
        session=session,
    )


@router.post(
    "/redemptions/{request_id}/cancel",
    response_model=RedemptionRequestSummary,
)
async def cancel_redemption(
    request_id: str,
    body: CancelRequest,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: InvestorOperationsService = Depends(get_investor_ops_service),
    session: AsyncSession = Depends(get_db),
) -> RedemptionRequestSummary:
    return await service.cancel_redemption(
        request_id,
        reason=body.reason,
        cancelled_by=body.cancelled_by,
        session=session,
    )


# ---------------------------------------------------------------------------
#  Fund terms endpoints
# ---------------------------------------------------------------------------


@router.get("/fund-terms", response_model=list[FundTermsSummary])
async def list_fund_terms(
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    service: InvestorOperationsService = Depends(get_investor_ops_service),
    session: AsyncSession = Depends(get_db),
) -> list[FundTermsSummary]:
    return await service.list_fund_terms(session=session)


@router.post("/fund-terms", response_model=FundTermsSummary)
async def create_fund_terms(
    body: CreateFundTermsRequest,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: InvestorOperationsService = Depends(get_investor_ops_service),
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
    service: InvestorOperationsService = Depends(get_investor_ops_service),
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
    service: InvestorOperationsService = Depends(get_investor_ops_service),
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
    service: InvestorOperationsService = Depends(get_investor_ops_service),
    session: AsyncSession = Depends(get_db),
) -> InvestorKYCInfo:
    return await service.screen_investor(
        investor_id=investor_id,
        name=body.name,
        entity_type=body.entity_type,
        tax_jurisdiction=body.tax_jurisdiction,
        session=session,
    )


# ---------------------------------------------------------------------------
#  Queue summary
# ---------------------------------------------------------------------------


@router.get("/queue", response_model=QueueSummary)
async def get_queue_summary(
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    service: InvestorOperationsService = Depends(get_investor_ops_service),
    session: AsyncSession = Depends(get_db),
) -> QueueSummary:
    return await service.get_queue_summary(session=session)
