"""AI analysis module wiring — LLM-backed analysis service."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.modules.ai_analysis.repositories import AnalysisResultRepository, ResearchNoteRepository
from app.modules.ai_analysis.services import AIAnalysisService

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.shared.database import TenantSessionFactory
    from app.shared.events import EventBus

logger = structlog.get_logger()


async def setup(
    app: FastAPI,
    sf: TenantSessionFactory,
    *,
    event_bus: EventBus | None = None,
    settings=None,
    **ctx,
) -> None:
    """Wire AI analysis module."""
    llm_adapter = ctx["llm_adapter"]

    result_repo = AnalysisResultRepository(sf)
    note_repo = ResearchNoteRepository(sf)

    svc = AIAnalysisService(
        result_repo=result_repo,
        note_repo=note_repo,
        llm_adapter=llm_adapter,
        session_factory=sf,
        event_bus=event_bus,
    )
    app.state.ai_analysis_service = svc
    logger.info("ai_analysis_module_ready")
