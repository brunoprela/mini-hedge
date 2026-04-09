"""FastAPI routes for investor operations — redemption workflows."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.modules.investor_operations.dependencies import get_redemption_service
from app.modules.investor_operations.interfaces import (
    GateCheckResult,
    QueueSummary,
    RedemptionRequestSummary,
)
from app.shared.auth import Permission, require_permission
from app.shared.database import get_db

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.investor_operations.services import RedemptionService
    from app.shared.auth.request_context import RequestContext

router = APIRouter(prefix="/investor-operations", tags=["investor-operations"])


# ---------------------------------------------------------------------------
#  Request schemas
# ---------------------------------------------------------------------------


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


class CancelRequest(BaseModel):
    reason: str
    cancelled_by: str


# ---------------------------------------------------------------------------
#  Redemption endpoints
# ---------------------------------------------------------------------------


@router.post("/redemptions", response_model=RedemptionRequestSummary)
async def submit_redemption(
    body: SubmitRedemptionRequest,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    service: RedemptionService = Depends(get_redemption_service),
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
    service: RedemptionService = Depends(get_redemption_service),
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
    service: RedemptionService = Depends(get_redemption_service),
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
    service: RedemptionService = Depends(get_redemption_service),
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
    service: RedemptionService = Depends(get_redemption_service),
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
    service: RedemptionService = Depends(get_redemption_service),
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
    service: RedemptionService = Depends(get_redemption_service),
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
    service: RedemptionService = Depends(get_redemption_service),
    session: AsyncSession = Depends(get_db),
) -> RedemptionRequestSummary:
    return await service.cancel_redemption(
        request_id,
        reason=body.reason,
        cancelled_by=body.cancelled_by,
        session=session,
    )


# ---------------------------------------------------------------------------
#  Queue summary
# ---------------------------------------------------------------------------


@router.get("/queue", response_model=QueueSummary)
async def get_queue_summary(
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    service: RedemptionService = Depends(get_redemption_service),
    session: AsyncSession = Depends(get_db),
) -> QueueSummary:
    return await service.get_queue_summary(session=session)
