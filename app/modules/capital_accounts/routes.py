"""FastAPI routes for the capital accounts module."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.modules.capital_accounts.dependencies import get_capital_account_service
from app.modules.capital_accounts.interface import (
    CapitalAccountSummary,
    CapitalTransaction,
    FundCapitalOverview,
    InvestorInfo,
)
from app.shared.auth import Permission, require_permission
from app.shared.database import get_db

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.capital_accounts.models import CapitalAccountRecord
    from app.modules.capital_accounts.service import CapitalAccountService
    from app.shared.request_context import RequestContext

router = APIRouter(prefix="/capital", tags=["capital-accounts"])


# ---- Request / Response schemas ----


class SubscriptionRequest(BaseModel):
    investor_id: str
    amount: Decimal
    nav_per_share: Decimal
    business_date: date
    portfolio_id: str | None = None
    currency: str = "USD"
    share_class: str = "default"
    notes: str | None = None


class RedemptionRequest(BaseModel):
    investor_id: str
    amount: Decimal
    nav_per_share: Decimal
    business_date: date
    portfolio_id: str | None = None
    currency: str = "USD"
    notes: str | None = None


# ---- Endpoints ----


@router.get("/investors", response_model=list[InvestorInfo])
async def list_investors(
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    capital_service: CapitalAccountService = Depends(get_capital_account_service),
    session: AsyncSession = Depends(get_db),
) -> list[InvestorInfo]:
    return await capital_service.list_investors(session=session)


@router.get("/accounts", response_model=list[CapitalAccountSummary])
async def list_capital_accounts(
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    capital_service: CapitalAccountService = Depends(get_capital_account_service),
    session: AsyncSession = Depends(get_db),
) -> list[CapitalAccountSummary]:
    return await capital_service.get_capital_accounts(session=session)


@router.get("/overview", response_model=FundCapitalOverview)
async def get_fund_overview(
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    capital_service: CapitalAccountService = Depends(get_capital_account_service),
    session: AsyncSession = Depends(get_db),
) -> FundCapitalOverview:
    return await capital_service.get_fund_overview(session=session)


@router.get(
    "/investors/{investor_id}/history",
    response_model=list[CapitalAccountSummary],
)
async def get_investor_history(
    investor_id: str,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    capital_service: CapitalAccountService = Depends(get_capital_account_service),
    session: AsyncSession = Depends(get_db),
) -> list[CapitalAccountSummary]:
    return await capital_service.get_investor_history(investor_id, session=session)


@router.get(
    "/investors/{investor_id}/transactions",
    response_model=list[CapitalTransaction],
)
async def get_investor_transactions(
    investor_id: str,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    capital_service: CapitalAccountService = Depends(get_capital_account_service),
    session: AsyncSession = Depends(get_db),
) -> list[CapitalTransaction]:
    return await capital_service.get_transactions(investor_id, session=session)


@router.post("/subscriptions", response_model=CapitalAccountSummary, status_code=201)
async def process_subscription(
    body: SubscriptionRequest,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    capital_service: CapitalAccountService = Depends(get_capital_account_service),
    session: AsyncSession = Depends(get_db),
) -> CapitalAccountSummary:
    record = await capital_service.process_subscription(
        investor_id=body.investor_id,
        amount=body.amount,
        nav_per_share=body.nav_per_share,
        business_date=body.business_date,
        portfolio_id=UUID(body.portfolio_id) if body.portfolio_id else None,
        currency=body.currency,
        share_class=body.share_class,
        notes=body.notes,
        session=session,
    )
    return await _record_to_summary(record, capital_service, session)


@router.post("/redemptions", response_model=CapitalAccountSummary, status_code=201)
async def process_redemption(
    body: RedemptionRequest,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    capital_service: CapitalAccountService = Depends(get_capital_account_service),
    session: AsyncSession = Depends(get_db),
) -> CapitalAccountSummary:
    record = await capital_service.process_redemption(
        investor_id=body.investor_id,
        amount=body.amount,
        nav_per_share=body.nav_per_share,
        business_date=body.business_date,
        portfolio_id=UUID(body.portfolio_id) if body.portfolio_id else None,
        currency=body.currency,
        notes=body.notes,
        session=session,
    )
    return await _record_to_summary(record, capital_service, session)


async def _record_to_summary(
    record: CapitalAccountRecord,
    capital_service: CapitalAccountService,
    session: AsyncSession,
) -> CapitalAccountSummary:
    """Convert a CapitalAccountRecord to a CapitalAccountSummary DTO."""
    investors = await capital_service.list_investors(session=session)
    inv_map = {str(i.id): i.name for i in investors}
    return CapitalAccountSummary(
        id=UUID(record.id),
        investor_id=UUID(record.investor_id),
        investor_name=inv_map.get(record.investor_id, "Unknown"),
        share_class=record.share_class,
        beginning_capital=record.beginning_capital,
        contributions=record.contributions,
        withdrawals=record.withdrawals,
        pnl_allocation=record.pnl_allocation,
        management_fee_allocation=record.management_fee_allocation,
        performance_fee_allocation=record.performance_fee_allocation,
        ending_capital=record.ending_capital,
        ownership_pct=record.ownership_pct,
        shares_held=record.shares_held,
        effective_date=record.effective_date,
    )
