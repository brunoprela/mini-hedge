"""FastAPI routes for quant research module."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from app.modules.quant_research.dependencies import get_quant_research_service
from app.modules.quant_research.interfaces import (
    FactorAnalysisResult,
    FactorDefinition,
    FactorExposure,
    FactorType,
    MarketRegime,
    PortfolioFactorDecomposition,
    RegimeAnalysis,
)
from app.shared.auth import Permission, require_permission
from app.shared.database import get_db, get_read_db

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.quant_research.services import QuantResearchService
    from app.shared.auth.request_context import RequestContext

router = APIRouter(prefix="/quant-research", tags=["quant-research"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class CreateFactorRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    factor_type: FactorType
    description: str = ""
    formula: str = ""
    parameters: dict | None = None


class PortfolioDecompositionRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    portfolio_weights: dict[str, Decimal]
    factor_names: list[str]


class RegimeDetectRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    prices: list[tuple[date, Decimal]]


# ---------------------------------------------------------------------------
# Factor endpoints
# ---------------------------------------------------------------------------


@router.post("/factors", response_model=FactorDefinition)
async def create_factor(
    body: CreateFactorRequest,
    request_context: RequestContext = require_permission(Permission.RISK_WRITE),
    service: QuantResearchService = Depends(get_quant_research_service),
    session: AsyncSession = Depends(get_db),
) -> FactorDefinition:
    return await service.create_factor(
        name=body.name,
        factor_type=body.factor_type,
        description=body.description,
        formula=body.formula,
        parameters=body.parameters,
        session=session,
    )


@router.get("/factors", response_model=list[FactorDefinition])
async def list_factors(
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: QuantResearchService = Depends(get_quant_research_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[FactorDefinition]:
    return await service.list_factors(session=session)


@router.get(
    "/factors/{factor_name}/exposures",
    response_model=list[FactorExposure],
)
async def get_factor_exposures(
    factor_name: str,
    as_of_date: date = Query(default_factory=date.today),
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: QuantResearchService = Depends(get_quant_research_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[FactorExposure]:
    factor_record = await service._factor_repo.get_by_name(factor_name, session=session)
    if factor_record is None:
        return []
    records = await service._factor_repo.get_exposures(
        factor_record.id, as_of_date, session=session
    )
    return [
        FactorExposure(
            factor_name=factor_name,
            instrument_id=r.instrument_id,
            exposure=r.exposure,
            z_score=r.z_score,
            as_of_date=r.as_of_date,
        )
        for r in records
    ]


@router.get(
    "/factors/{factor_name}/analysis",
    response_model=FactorAnalysisResult,
)
async def get_factor_analysis(
    factor_name: str,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: QuantResearchService = Depends(get_quant_research_service),
    session: AsyncSession = Depends(get_read_db),
) -> FactorAnalysisResult:
    return await service.analyze_factor(
        factor_name,
        start_date=start_date,
        end_date=end_date,
        session=session,
    )


@router.post(
    "/portfolio-decomposition",
    response_model=PortfolioFactorDecomposition,
)
async def decompose_portfolio(
    body: PortfolioDecompositionRequest,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: QuantResearchService = Depends(get_quant_research_service),
    session: AsyncSession = Depends(get_read_db),
) -> PortfolioFactorDecomposition:
    return await service.decompose_portfolio(
        portfolio_weights=body.portfolio_weights,
        factor_names=body.factor_names,
        session=session,
    )


# ---------------------------------------------------------------------------
# Regime endpoints
# ---------------------------------------------------------------------------


@router.post("/regime/detect", response_model=RegimeAnalysis)
async def detect_regime(
    body: RegimeDetectRequest,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: QuantResearchService = Depends(get_quant_research_service),
    session: AsyncSession = Depends(get_db),
) -> RegimeAnalysis:
    return await service.detect_regime(body.prices, session=session)


@router.get("/regime/current", response_model=MarketRegime | None)
async def get_current_regime(
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: QuantResearchService = Depends(get_quant_research_service),
    session: AsyncSession = Depends(get_read_db),
) -> MarketRegime | None:
    return await service.get_current_regime(session=session)


@router.get("/regime/history", response_model=list[MarketRegime])
async def get_regime_history(
    limit: int = Query(default=100, le=500),
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: QuantResearchService = Depends(get_quant_research_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[MarketRegime]:
    return await service.get_regime_history(limit=limit, session=session)
