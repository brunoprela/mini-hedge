"""FastAPI routes for regulatory reporting."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query

from app.modules.regulatory.dependencies import get_regulatory_service
from app.modules.regulatory.interface import (
    Filing13FReport,
    FormPFData,
    InvestorStatement,
    MonthlyPerformanceLetter,
)
from app.shared.auth import Permission, require_permission
from app.shared.database import get_db

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.regulatory.service import RegulatoryService
    from app.shared.auth.request_context import RequestContext

router = APIRouter(prefix="/regulatory", tags=["regulatory"])


# -- Form PF --


@router.post("/form-pf", response_model=FormPFData)
async def generate_form_pf(
    fund_slug: str = Query(...),
    reporting_date: date = Query(...),
    fund_name: str = Query(""),
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    svc: RegulatoryService = Depends(get_regulatory_service),
    session: AsyncSession = Depends(get_db),
) -> FormPFData:
    return await svc.generate_form_pf(
        fund_slug,
        reporting_date,
        fund_name=fund_name,
        session=session,
    )


# -- 13F --


@router.post("/13f", response_model=Filing13FReport)
async def generate_13f(
    fund_slug: str = Query(...),
    reporting_date: date = Query(...),
    fund_name: str = Query(""),
    portfolio_ids: str = Query(""),
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    svc: RegulatoryService = Depends(get_regulatory_service),
    session: AsyncSession = Depends(get_db),
) -> Filing13FReport:
    pids = [p.strip() for p in portfolio_ids.split(",") if p.strip()] or None
    return await svc.generate_13f(
        fund_slug,
        reporting_date,
        fund_name=fund_name,
        portfolio_ids=pids,
        session=session,
    )


# -- Investor Statements --


@router.post("/investor-statement", response_model=InvestorStatement | None)
async def generate_investor_statement(
    investor_id: str = Query(...),
    period_start: date = Query(...),
    period_end: date = Query(...),
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    svc: RegulatoryService = Depends(get_regulatory_service),
    session: AsyncSession = Depends(get_db),
) -> InvestorStatement | None:
    return await svc.generate_investor_statement(
        investor_id,
        period_start,
        period_end,
        session=session,
    )


# -- Performance Letters --


@router.post("/performance-letter", response_model=MonthlyPerformanceLetter)
async def generate_performance_letter(
    fund_slug: str = Query(...),
    period_end: date = Query(...),
    fund_name: str = Query(""),
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    svc: RegulatoryService = Depends(get_regulatory_service),
    session: AsyncSession = Depends(get_db),
) -> MonthlyPerformanceLetter:
    return await svc.generate_performance_letter(
        fund_slug,
        period_end,
        fund_name=fund_name,
        session=session,
    )


# -- Filing history --


@router.get("/filings")
async def list_filings(
    filing_type: str | None = Query(None),
    _ctx: RequestContext = require_permission(Permission.CAPITAL_READ),
    svc: RegulatoryService = Depends(get_regulatory_service),
    session: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await svc.list_filings(filing_type=filing_type, session=session)
