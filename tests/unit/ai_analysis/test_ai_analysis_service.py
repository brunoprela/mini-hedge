"""Unit tests for AIAnalysisService — mocked LLM/repo, real event bus."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.ai_analysis.core.insight_engine import generate_portfolio_insights
from app.modules.ai_analysis.interfaces import AnalysisRequest, AnalysisType, SentimentScore
from app.modules.ai_analysis.services import AIAnalysisService
from app.shared.adapters.llm import LLMResponse
from app.shared.audit.events import AuditEventType
from app.shared.events import InProcessEventBus
from tests.helpers import EventCapture

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NOW = datetime.now(UTC)
FAKE_UUID = str(uuid4())


def _make_llm_response(text: str, model: str = "gpt-4o", tokens: int = 512) -> LLMResponse:
    return LLMResponse(text=text, model=model, tokens_used=tokens)


def _make_record_mock(record_id: str | None = None) -> MagicMock:
    """Simulate a saved AnalysisResultRecord / ResearchNoteRecord."""
    record = MagicMock()
    record.id = record_id or str(uuid4())
    record.created_at = NOW
    record.key_points = []
    record.instruments = ["AAPL"]
    record.model_used = "gpt-4o"
    record.tokens_used = 512
    record.request_context = {}
    record.sentiment = None
    record.confidence = None
    record.summary = "Summary"
    record.body = "Body"
    record.title = "Note title"
    record.content = "Note content"
    record.analysis_type = AnalysisType.MARKET_COMMENTARY.value
    record.tags = []
    return record


@pytest.fixture
def event_bus() -> InProcessEventBus:
    return InProcessEventBus()


@pytest.fixture
def capture(event_bus: InProcessEventBus) -> EventCapture:
    cap = EventCapture()
    cap.wire_to_bus(event_bus, ["shared.audit"])
    return cap


@pytest.fixture
def analysis_repo() -> AsyncMock:
    repo = AsyncMock()

    # save_result mutates the passed record (assigns id/created_at server-side)
    async def _save_result(record, *, session=None):
        record.id = FAKE_UUID
        record.created_at = NOW

    repo.save_result.side_effect = _save_result
    return repo


@pytest.fixture
def note_repo() -> AsyncMock:
    repo = AsyncMock()

    async def _save_note(record, *, session=None):
        record.id = FAKE_UUID
        record.created_at = NOW

    repo.save_note.side_effect = _save_note
    return repo


@pytest.fixture
def llm() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def session_factory() -> MagicMock:
    sf = MagicMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=None)
    cm.__aexit__ = AsyncMock(return_value=False)
    sf.fund_scope.return_value = cm
    return sf


@pytest.fixture
def service(
    analysis_repo: AsyncMock,
    note_repo: AsyncMock,
    llm: AsyncMock,
    session_factory: MagicMock,
    event_bus: InProcessEventBus,
) -> AIAnalysisService:
    return AIAnalysisService(
        result_repo=analysis_repo,
        note_repo=note_repo,
        llm_adapter=llm,
        session_factory=session_factory,
        event_bus=event_bus,
    )


# ---------------------------------------------------------------------------
# run_analysis — structured JSON response
# ---------------------------------------------------------------------------


class TestRunAnalysisStructuredJSON:
    async def test_result_fields_populated_from_json(
        self, service: AIAnalysisService, llm: AsyncMock
    ):
        payload = {
            "summary": "Markets sold off on inflation data.",
            "body": "Long body text here.",
            "key_points": ["Point A", "Point B"],
            "sentiment": "bearish",
            "confidence": "0.82",
        }
        llm.generate.return_value = _make_llm_response(json.dumps(payload))

        request = AnalysisRequest(
            analysis_type=AnalysisType.MARKET_COMMENTARY,
            context={"market_data": {"spx": -1.2}},
            instruments=["SPY"],
        )
        result = await service.run_analysis(request)

        assert result.summary == "Markets sold off on inflation data."
        assert result.sentiment == SentimentScore.BEARISH
        assert result.confidence == Decimal("0.82")
        assert "Point A" in result.key_points
        assert result.model_used == "gpt-4o"
        assert result.tokens_used == 512

    async def test_data_sources_derived_from_context_keys(
        self, service: AIAnalysisService, llm: AsyncMock
    ):
        payload = {"summary": "ok", "body": "ok", "key_points": [], "sentiment": "neutral"}
        llm.generate.return_value = _make_llm_response(json.dumps(payload))

        request = AnalysisRequest(
            analysis_type=AnalysisType.RISK_ASSESSMENT,
            context={"risk_metrics": {}, "positions": []},
            instruments=["AAPL"],
        )
        result = await service.run_analysis(request)

        assert "risk_engine" in result.data_sources
        assert "portfolio_positions" in result.data_sources
        assert "security_master" in result.data_sources  # instruments present


# ---------------------------------------------------------------------------
# run_analysis — plain text fallback
# ---------------------------------------------------------------------------


class TestRunAnalysisPlainTextFallback:
    async def test_non_json_falls_back_gracefully(self, service: AIAnalysisService, llm: AsyncMock):
        plain = "This is a plain text market summary without any JSON structure."
        llm.generate.return_value = _make_llm_response(plain)

        request = AnalysisRequest(
            analysis_type=AnalysisType.MARKET_COMMENTARY,
            context={"news": "Fed holds rates"},
        )
        result = await service.run_analysis(request)

        assert result.summary == plain[:500]
        assert result.body == plain
        assert result.key_points == []
        assert result.sentiment is None
        assert result.confidence is None

    async def test_repo_save_called_on_fallback(
        self, service: AIAnalysisService, llm: AsyncMock, analysis_repo: AsyncMock
    ):
        llm.generate.return_value = _make_llm_response("plain text response")

        request = AnalysisRequest(
            analysis_type=AnalysisType.NEWS_DIGEST,
            context={"news": "Something happened"},
        )
        await service.run_analysis(request)

        analysis_repo.save_result.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_portfolio_insights — rules-based, no LLM
# ---------------------------------------------------------------------------


class TestGetPortfolioInsights:
    async def test_concentration_risk_flagged(self, service: AIAnalysisService):
        positions = [
            {"instrument_id": "AAPL", "market_value": 600_000, "sector": "Technology"},
            {"instrument_id": "MSFT", "market_value": 400_000, "sector": "Technology"},
        ]
        insights = await service.get_portfolio_insights(positions)

        types = {i.insight_type for i in insights}
        assert "concentration_risk" in types

    async def test_sector_overweight_flagged(self, service: AIAnalysisService):
        positions = [
            {"instrument_id": "AAPL", "market_value": 400_000, "sector": "Technology"},
            {"instrument_id": "MSFT", "market_value": 400_000, "sector": "Technology"},
            {"instrument_id": "GOOG", "market_value": 200_000, "sector": "Technology"},
        ]
        insights = await service.get_portfolio_insights(positions)

        sector_insights = [i for i in insights if i.insight_type == "sector_concentration"]
        assert len(sector_insights) >= 1
        assert sector_insights[0].severity == "warning"

    async def test_empty_positions_returns_no_insights(self, service: AIAnalysisService):
        insights = await service.get_portfolio_insights([])
        assert insights == []

    async def test_factor_tilt_flagged_via_insight_engine_directly(self):
        positions = [
            {"instrument_id": "X", "market_value": 1000, "sector": "Energy"},
        ]
        factor_exposures = {"momentum": 2.5, "value": -0.3}
        insights = generate_portfolio_insights(positions, factor_exposures=factor_exposures)

        tilt_insights = [i for i in insights if i.insight_type == "factor_tilt"]
        assert len(tilt_insights) == 1
        assert "momentum" in tilt_insights[0].title


# ---------------------------------------------------------------------------
# create_research_note — persistence
# ---------------------------------------------------------------------------


class TestCreateResearchNote:
    async def test_note_persisted_and_returned(
        self, service: AIAnalysisService, note_repo: AsyncMock
    ):
        note = await service.create_research_note(
            title="Tech Sector Outlook",
            content="Detailed analysis of the tech sector.",
            analysis_type=AnalysisType.PORTFOLIO_REVIEW,
            instruments=["AAPL", "MSFT"],
            tags=["tech", "q1-2026"],
        )

        note_repo.save_note.assert_awaited_once()
        assert note.title == "Tech Sector Outlook"
        assert note.instruments == ["AAPL", "MSFT"]
        assert note.tags == ["tech", "q1-2026"]
        assert note.analysis_type == AnalysisType.PORTFOLIO_REVIEW


# ---------------------------------------------------------------------------
# Event publishing
# ---------------------------------------------------------------------------


class TestEventPublishing:
    async def test_analysis_completed_event_published(
        self, service: AIAnalysisService, llm: AsyncMock, capture: EventCapture
    ):
        payload = {"summary": "ok", "body": "ok", "key_points": [], "sentiment": "bullish"}
        llm.generate.return_value = _make_llm_response(json.dumps(payload))

        request = AnalysisRequest(
            analysis_type=AnalysisType.TRADE_RATIONALE,
            context={"prices": [150, 155]},
            instruments=["AAPL"],
        )
        await service.run_analysis(request)

        audit_events = capture.get_by_topic("audit")
        completed = [e for e in audit_events if e.event_type == AuditEventType.ANALYSIS_COMPLETED]
        assert len(completed) == 1
        assert completed[0].data["analysis_type"] == AnalysisType.TRADE_RATIONALE.value
        assert "AAPL" in completed[0].data["instruments"]

    async def test_research_note_created_event_published(
        self, service: AIAnalysisService, note_repo: AsyncMock, capture: EventCapture
    ):
        await service.create_research_note(
            title="Macro Update",
            content="Fed kept rates unchanged.",
            analysis_type=AnalysisType.MARKET_COMMENTARY,
            tags=["macro"],
        )

        audit_events = capture.get_by_topic("audit")
        note_events = [
            e for e in audit_events if e.event_type == AuditEventType.RESEARCH_NOTE_CREATED
        ]
        assert len(note_events) == 1
        assert note_events[0].data["title"] == "Macro Update"
        assert "macro" in note_events[0].data["tags"]
