"""FastAPI routes for investor operations — subscription workflows."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.investor_operations.dependencies import get_subscription_service
from app.modules.investor_operations.interfaces import SubscriptionRequestSummary
from app.modules.investor_operations.services import SubscriptionService
from app.shared.auth import Permission, require_permission
from app.shared.auth.request_context import RequestContext
from app.shared.database import get_db

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


class ExecuteRequest(BaseModel):
    dealing_date: date
    nav_per_share: Decimal
    portfolio_id: UUID


# ---------------------------------------------------------------------------
#  Subscription endpoints
# ---------------------------------------------------------------------------


@router.post("/subscriptions", response_model=SubscriptionRequestSummary)
async def submit_subscription(
    body: SubmitSubscriptionRequest,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: SubscriptionService = Depends(get_subscription_service),
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
    service: SubscriptionService = Depends(get_subscription_service),
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
    service: SubscriptionService = Depends(get_subscription_service),
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
    service: SubscriptionService = Depends(get_subscription_service),
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
    service: SubscriptionService = Depends(get_subscription_service),
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
    service: SubscriptionService = Depends(get_subscription_service),
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
    service: SubscriptionService = Depends(get_subscription_service),
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
    service: SubscriptionService = Depends(get_subscription_service),
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
    service: SubscriptionService = Depends(get_subscription_service),
    session: AsyncSession = Depends(get_db),
) -> list[SubscriptionRequestSummary]:
    return await service.execute_subscriptions(
        dealing_date=body.dealing_date,
        nav_per_share=body.nav_per_share,
        portfolio_id=body.portfolio_id,
        session=session,
    )
