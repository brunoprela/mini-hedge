"""AI analysis service — orchestrates LLM calls and persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from app.modules.ai_analysis.insight_engine import generate_portfolio_insights
from app.modules.ai_analysis.interface import (
    AnalysisRequest,
    AnalysisResult,
    AnalysisType,
    PortfolioInsight,
    ResearchNote,
    SentimentScore,
)
from app.modules.ai_analysis.models import AnalysisResultRecord, ResearchNoteRecord
from app.modules.ai_analysis.prompts import build_prompt

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.ai_analysis.llm_adapter import LLMAdapter
    from app.modules.ai_analysis.repository import AnalysisRepository
    from app.shared.database import TenantSessionFactory
    from app.shared.events import EventBus

logger = structlog.get_logger()


class AIAnalysisService:
    """Orchestrates AI analysis, insight generation, and persistence."""

    def __init__(
        self,
        repo: AnalysisRepository,
        llm_adapter: LLMAdapter,
        session_factory: TenantSessionFactory,
        event_bus: EventBus | None = None,
    ) -> None:
        self._repo = repo
        self._llm = llm_adapter
        self._session_factory = session_factory
        self._event_bus = event_bus

    async def run_analysis(
        self, request: AnalysisRequest, *, session: AsyncSession | None = None
    ) -> AnalysisResult:
        """Run an LLM-based analysis and persist the result."""
        prompt = build_prompt(request.analysis_type, request.context)
        llm_response = await self._llm.generate(prompt)

        # Parse structured response from LLM
        try:
            parsed = json.loads(llm_response.text)
        except json.JSONDecodeError:
            parsed = {
                "summary": llm_response.text[:500],
                "body": llm_response.text,
                "key_points": [],
                "sentiment": None,
                "confidence": None,
            }

        sentiment = _parse_sentiment(parsed.get("sentiment"))
        confidence = _parse_confidence(parsed.get("confidence"))

        # Track which data sources informed this analysis
        data_sources = _extract_data_sources(request)

        record = AnalysisResultRecord(
            analysis_type=request.analysis_type.value,
            request_context={**request.context, "_data_sources": data_sources},
            summary=str(parsed.get("summary", "")),
            body=str(parsed.get("body", "")),
            sentiment=sentiment.value if sentiment else None,
            confidence=confidence,
            key_points=parsed.get("key_points", []),
            instruments=request.instruments,
            model_used=llm_response.model,
            tokens_used=llm_response.tokens_used,
        )
        await self._repo.save_result(record, session=session)

        if self._event_bus:
            from app.shared.audit.events import AuditEventType
            from app.shared.events import BaseEvent
            from app.shared.schema_registry import shared_topic

            await self._event_bus.publish(
                shared_topic("audit"),
                BaseEvent(
                    event_type=AuditEventType.ANALYSIS_COMPLETED,
                    data={
                        "analysis_id": record.id,
                        "analysis_type": request.analysis_type.value,
                        "model_used": llm_response.model,
                        "tokens_used": llm_response.tokens_used,
                        "instruments": request.instruments or [],
                    },
                ),
            )

        return AnalysisResult(
            id=UUID(record.id),
            analysis_type=request.analysis_type,
            summary=record.summary,
            body=record.body,
            sentiment=sentiment,
            confidence=confidence,
            key_points=record.key_points,
            instruments_mentioned=request.instruments,
            data_sources=data_sources,
            model_used=record.model_used,
            tokens_used=record.tokens_used,
            created_at=record.created_at or datetime.now(tz=UTC),
        )

    async def get_portfolio_insights(
        self,
        positions: list[dict],
        *,
        risk_metrics: dict | None = None,
        factor_exposures: dict | None = None,
        session: AsyncSession | None = None,  # noqa: ARG002
    ) -> list[PortfolioInsight]:
        """Generate rules-based portfolio insights."""
        return generate_portfolio_insights(
            positions,
            risk_metrics=risk_metrics,
            factor_exposures=factor_exposures,
        )

    async def get_analysis_history(
        self,
        *,
        analysis_type: AnalysisType | None = None,
        limit: int = 50,
        session: AsyncSession | None = None,
    ) -> list[AnalysisResult]:
        """Retrieve past analysis results."""
        type_str = analysis_type.value if analysis_type else None
        records = await self._repo.list_results(
            analysis_type=type_str, limit=limit, session=session
        )
        return [_record_to_result(r) for r in records]

    async def create_research_note(
        self,
        title: str,
        content: str,
        analysis_type: AnalysisType,
        instruments: list[str] | None = None,
        tags: list[str] | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> ResearchNote:
        """Create and persist a research note."""
        record = ResearchNoteRecord(
            title=title,
            content=content,
            analysis_type=analysis_type.value,
            instruments=instruments or [],
            tags=tags or [],
        )
        await self._repo.save_note(record, session=session)

        if self._event_bus:
            from app.shared.audit.events import AuditEventType
            from app.shared.events import BaseEvent
            from app.shared.schema_registry import shared_topic

            await self._event_bus.publish(
                shared_topic("audit"),
                BaseEvent(
                    event_type=AuditEventType.RESEARCH_NOTE_CREATED,
                    data={
                        "note_id": record.id,
                        "title": title,
                        "analysis_type": analysis_type.value,
                        "instruments": instruments or [],
                        "tags": tags or [],
                    },
                ),
            )

        return ResearchNote(
            id=UUID(record.id),
            title=record.title,
            content=record.content,
            analysis_type=analysis_type,
            instruments=record.instruments,
            tags=record.tags,
            created_at=record.created_at or datetime.now(tz=UTC),
        )

    async def list_research_notes(
        self,
        *,
        tags: list[str] | None = None,
        limit: int = 50,
        session: AsyncSession | None = None,
    ) -> list[ResearchNote]:
        """List research notes with optional tag filter."""
        records = await self._repo.list_notes(tags=tags, limit=limit, session=session)
        return [_note_record_to_dto(r) for r in records]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_sentiment(value: object) -> SentimentScore | None:
    if value is None:
        return None
    try:
        return SentimentScore(str(value))
    except ValueError:
        return None


def _parse_confidence(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


def _extract_data_sources(request: AnalysisRequest) -> list[str]:
    """Derive data source labels from the context keys and analysis type."""
    sources: list[str] = []
    source_map = {
        "positions": "portfolio_positions",
        "risk_metrics": "risk_engine",
        "factor_exposures": "factor_model",
        "market_data": "market_data_feed",
        "news": "news_feed",
        "earnings": "earnings_data",
        "filings": "sec_filings",
        "sentiment": "sentiment_feed",
        "prices": "price_history",
        "returns": "return_series",
    }
    for key in request.context:
        if key in source_map:
            sources.append(source_map[key])
    if request.instruments:
        sources.append("security_master")
    if not sources:
        sources.append(f"{request.analysis_type.value}_context")
    return sources


def _record_to_result(record: AnalysisResultRecord) -> AnalysisResult:
    ctx = record.request_context or {}
    data_sources = ctx.get("_data_sources", [])
    return AnalysisResult(
        id=UUID(record.id),
        analysis_type=AnalysisType(record.analysis_type),
        summary=record.summary,
        body=record.body,
        sentiment=_parse_sentiment(record.sentiment),
        confidence=record.confidence,
        key_points=record.key_points or [],
        instruments_mentioned=record.instruments or [],
        data_sources=data_sources,
        model_used=record.model_used,
        tokens_used=record.tokens_used,
        created_at=record.created_at,
    )


def _note_record_to_dto(record: ResearchNoteRecord) -> ResearchNote:
    return ResearchNote(
        id=UUID(record.id),
        title=record.title,
        content=record.content,
        analysis_type=AnalysisType(record.analysis_type),
        instruments=record.instruments or [],
        tags=record.tags or [],
        created_at=record.created_at,
    )
