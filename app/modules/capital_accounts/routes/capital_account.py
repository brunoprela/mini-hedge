"""FastAPI routes for the capital accounts module."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.capital_accounts.dependencies import (
    get_capital_account_service,
    get_capital_transaction_service,
    get_investor_repo,
)
from app.modules.capital_accounts.interfaces import (
    CapitalAccountSummary,
    CapitalTransaction,
    FundCapitalOverview,
    InvestorInfo,
    ShareClassSummary,
)
from app.modules.capital_accounts.models.capital_account import CapitalAccountRecord
from app.modules.capital_accounts.repositories.investor import InvestorRepository
from app.modules.capital_accounts.services import CapitalAccountService
from app.modules.capital_accounts.services.capital_transaction import CapitalTransactionService
from app.modules.platform.models.investor import InvestorRecord
from app.shared.auth import Permission, require_permission
from app.shared.auth.request_context import RequestContext
from app.shared.database import get_db

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
    share_class: str = "default"
    notes: str | None = None


class CreateInvestorRequest(BaseModel):
    name: str
    entity_type: str = "institution"
    tax_jurisdiction: str = "US"
    contact_email: str | None = None


class UpdateInvestorRequest(BaseModel):
    name: str | None = None
    entity_type: str | None = None
    tax_jurisdiction: str | None = None
    contact_email: str | None = None
    is_active: bool | None = None


# ---- Endpoints ----


@router.get("/investors", response_model=list[InvestorInfo])
async def list_investors(
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    capital_service: CapitalAccountService = Depends(get_capital_account_service),
    session: AsyncSession = Depends(get_db),
) -> list[InvestorInfo]:
    return await capital_service.list_investors(session=session)


@router.post("/investors", response_model=InvestorInfo, status_code=201)
async def create_investor(
    body: CreateInvestorRequest,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    investor_repo: InvestorRepository = Depends(get_investor_repo),
    session: AsyncSession = Depends(get_db),
) -> InvestorInfo:
    record = InvestorRecord(
        name=body.name,
        entity_type=body.entity_type,
        tax_jurisdiction=body.tax_jurisdiction,
        contact_email=body.contact_email or "",
        is_active=True,
    )
    await investor_repo.insert(record, session=session)
    return InvestorInfo(
        id=record.id,
        name=record.name,
        entity_type=record.entity_type,
        tax_jurisdiction=record.tax_jurisdiction,
        contact_email=record.contact_email,
        is_active=record.is_active,
    )


@router.get("/investors/{investor_id}", response_model=InvestorInfo)
async def get_investor(
    investor_id: str,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    investor_repo: InvestorRepository = Depends(get_investor_repo),
    session: AsyncSession = Depends(get_db),
) -> InvestorInfo:
    record = await investor_repo.get_by_id(investor_id, session=session)
    if record is None:
        raise HTTPException(status_code=404, detail="Investor not found")
    return InvestorInfo(
        id=record.id,
        name=record.name,
        entity_type=record.entity_type,
        tax_jurisdiction=record.tax_jurisdiction,
        contact_email=record.contact_email,
        is_active=record.is_active,
    )


@router.patch("/investors/{investor_id}", response_model=InvestorInfo)
async def update_investor(
    investor_id: str,
    body: UpdateInvestorRequest,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    investor_repo: InvestorRepository = Depends(get_investor_repo),
    session: AsyncSession = Depends(get_db),
) -> InvestorInfo:
    record = await investor_repo.update(
        investor_id,
        name=body.name,
        entity_type=body.entity_type,
        tax_jurisdiction=body.tax_jurisdiction,
        contact_email=body.contact_email,
        is_active=body.is_active,
        session=session,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Investor not found")
    return InvestorInfo(
        id=record.id,
        name=record.name,
        entity_type=record.entity_type,
        tax_jurisdiction=record.tax_jurisdiction,
        contact_email=record.contact_email,
        is_active=record.is_active,
    )


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
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    capital_service: CapitalAccountService = Depends(get_capital_account_service),
    session: AsyncSession = Depends(get_db),
) -> list[CapitalAccountSummary]:
    return await capital_service.get_investor_history(
        investor_id, from_date=from_date, to_date=to_date, session=session
    )


@router.get(
    "/investors/{investor_id}/transactions",
    response_model=list[CapitalTransaction],
)
async def get_investor_transactions(
    investor_id: str,
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    capital_service: CapitalAccountService = Depends(get_capital_account_service),
    session: AsyncSession = Depends(get_db),
) -> list[CapitalTransaction]:
    return await capital_service.get_transactions(
        investor_id, from_date=from_date, to_date=to_date, session=session
    )


@router.post("/subscriptions", response_model=CapitalAccountSummary, status_code=201)
async def process_subscription(
    body: SubscriptionRequest,
    _ctx: RequestContext = require_permission(Permission.CAPITAL_WRITE),
    capital_service: CapitalAccountService = Depends(get_capital_account_service),
    txn_service: CapitalTransactionService = Depends(get_capital_transaction_service),
    session: AsyncSession = Depends(get_db),
) -> CapitalAccountSummary:
    record = await txn_service.process_subscription(
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
    txn_service: CapitalTransactionService = Depends(get_capital_transaction_service),
    session: AsyncSession = Depends(get_db),
) -> CapitalAccountSummary:
    record = await txn_service.process_redemption(
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


@router.get("/share-classes", response_model=list[ShareClassSummary])
async def list_share_classes(
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    capital_service: CapitalAccountService = Depends(get_capital_account_service),
    session: AsyncSession = Depends(get_db),
) -> list[ShareClassSummary]:
    classes = await capital_service.list_share_classes(session=session)
    result: list[ShareClassSummary] = []
    for cls in classes:
        aum, shares, nav = await capital_service.get_share_class_nav(cls, session=session)
        investor_count = await capital_service.get_share_class_investor_count(
            cls, session=session
        )
        result.append(
            ShareClassSummary(
                share_class=cls,
                total_aum=aum,
                total_shares=shares,
                nav_per_share=nav,
                investor_count=investor_count,
            )
        )
    return result


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
