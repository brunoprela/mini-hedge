"""FastAPI routes for AI analysis."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from app.modules.ai_analysis.dependencies import get_ai_analysis_service
from app.modules.ai_analysis.interface import (
    AnalysisResult,
    AnalysisType,
    PortfolioInsight,
    ResearchNote,
)
from app.shared.auth import Permission, require_permission
from app.shared.database import get_db, get_read_db

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.ai_analysis.service import AIAnalysisService
    from app.shared.request_context import RequestContext

router = APIRouter(prefix="/ai-analysis", tags=["ai-analysis"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class AnalyzeRequestBody(BaseModel):
    model_config = ConfigDict(frozen=True)

    analysis_type: AnalysisType
    context: dict[str, Any]
    instruments: list[str] = []


class PortfolioInsightsRequestBody(BaseModel):
    model_config = ConfigDict(frozen=True)

    positions: list[dict[str, Any]]
    risk_metrics: dict[str, Any] | None = None
    factor_exposures: dict[str, float] | None = None


class CreateResearchNoteBody(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    content: str
    analysis_type: AnalysisType
    instruments: list[str] = []
    tags: list[str] = []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/analyze", response_model=AnalysisResult)
async def run_analysis(
    body: AnalyzeRequestBody,
    request_context: RequestContext = require_permission(Permission.RISK_WRITE),  # noqa: ARG001
    service: AIAnalysisService = Depends(get_ai_analysis_service),
    session: AsyncSession = Depends(get_db),
) -> AnalysisResult:
    """Run an AI-driven analysis."""
    from app.modules.ai_analysis.interface import AnalysisRequest

    request = AnalysisRequest(
        analysis_type=body.analysis_type,
        context=body.context,
        instruments=body.instruments,
    )
    return await service.run_analysis(request, session=session)


@router.get("/history", response_model=list[AnalysisResult])
async def get_analysis_history(
    analysis_type: AnalysisType | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    request_context: RequestContext = require_permission(Permission.RISK_READ),  # noqa: ARG001
    service: AIAnalysisService = Depends(get_ai_analysis_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[AnalysisResult]:
    """Retrieve analysis history."""
    return await service.get_analysis_history(
        analysis_type=analysis_type, limit=limit, session=session
    )


@router.get("/results/{result_id}", response_model=AnalysisResult)
async def get_result(
    result_id: UUID,
    request_context: RequestContext = require_permission(Permission.RISK_READ),  # noqa: ARG001
    service: AIAnalysisService = Depends(get_ai_analysis_service),
    session: AsyncSession = Depends(get_read_db),
) -> AnalysisResult:
    """Get a specific analysis result."""
    from fastapi import HTTPException

    from app.modules.ai_analysis.service import _record_to_result

    record = await service._repo.get_result(str(result_id), session=session)
    if record is None:
        raise HTTPException(status_code=404, detail="Analysis result not found")
    return _record_to_result(record)


@router.post("/portfolio-insights", response_model=list[PortfolioInsight])
async def get_portfolio_insights(
    body: PortfolioInsightsRequestBody,
    request_context: RequestContext = require_permission(Permission.RISK_READ),  # noqa: ARG001
    service: AIAnalysisService = Depends(get_ai_analysis_service),
) -> list[PortfolioInsight]:
    """Generate rules-based portfolio insights from position data."""
    return await service.get_portfolio_insights(
        body.positions,
        risk_metrics=body.risk_metrics,
        factor_exposures=body.factor_exposures,
    )


@router.post("/research-notes", response_model=ResearchNote)
async def create_research_note(
    body: CreateResearchNoteBody,
    request_context: RequestContext = require_permission(Permission.RISK_WRITE),  # noqa: ARG001
    service: AIAnalysisService = Depends(get_ai_analysis_service),
    session: AsyncSession = Depends(get_db),
) -> ResearchNote:
    """Create a research note."""
    return await service.create_research_note(
        title=body.title,
        content=body.content,
        analysis_type=body.analysis_type,
        instruments=body.instruments,
        tags=body.tags,
        session=session,
    )


@router.get("/research-notes", response_model=list[ResearchNote])
async def list_research_notes(
    tags: list[str] | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    request_context: RequestContext = require_permission(Permission.RISK_READ),  # noqa: ARG001
    service: AIAnalysisService = Depends(get_ai_analysis_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[ResearchNote]:
    """List research notes with optional tag filter."""
    return await service.list_research_notes(tags=tags, limit=limit, session=session)


@router.get("/research-notes/{note_id}", response_model=ResearchNote)
async def get_research_note(
    note_id: UUID,
    request_context: RequestContext = require_permission(Permission.RISK_READ),  # noqa: ARG001
    service: AIAnalysisService = Depends(get_ai_analysis_service),
    session: AsyncSession = Depends(get_read_db),
) -> ResearchNote:
    """Get a specific research note."""
    from fastapi import HTTPException

    from app.modules.ai_analysis.service import _note_record_to_dto

    record = await service._repo.get_note(str(note_id), session=session)
    if record is None:
        raise HTTPException(status_code=404, detail="Research note not found")
    return _note_record_to_dto(record)


@router.delete("/research-notes/{note_id}", status_code=204)
async def delete_research_note(
    note_id: UUID,
    request_context: RequestContext = require_permission(Permission.RISK_WRITE),  # noqa: ARG001
    service: AIAnalysisService = Depends(get_ai_analysis_service),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a research note."""
    await service._repo.delete_note(str(note_id), session=session)
