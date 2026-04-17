"""Unit tests for AIAnalysisService helper functions and uncovered service methods."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.ai_analysis.interfaces import (
    AnalysisRequest,
    AnalysisType,
    SentimentScore,
)
from app.modules.ai_analysis.services import AIAnalysisService
from app.modules.ai_analysis.services.analysis import (
    _extract_data_sources,
    _note_record_to_dto,
    _parse_confidence,
    _parse_sentiment,
    _record_to_result,
)

NOW = datetime.now(UTC)
FAKE_UUID = str(uuid4())


def _make_record_mock(**overrides) -> MagicMock:
    record = MagicMock()
    record.id = overrides.get("id", str(uuid4()))
    record.created_at = overrides.get("created_at", NOW)
    record.key_points = overrides.get("key_points", ["point1"])
    record.instruments = overrides.get("instruments", ["AAPL"])
    record.model_used = overrides.get("model_used", "gpt-4o")
    record.tokens_used = overrides.get("tokens_used", 512)
    record.request_context = overrides.get("request_context", {})
    record.sentiment = overrides.get("sentiment", None)
    record.confidence = overrides.get("confidence", Decimal("0.75"))
    record.summary = overrides.get("summary", "A summary")
    record.body = overrides.get("body", "A body")
    record.analysis_type = overrides.get("analysis_type", AnalysisType.RISK_ASSESSMENT.value)
    record.title = overrides.get("title", "A title")
    record.content = overrides.get("content", "Content body")
    record.tags = overrides.get("tags", ["macro"])
    return record


def _make_service(
    *,
    result_repo: AsyncMock | None = None,
    note_repo: AsyncMock | None = None,
    llm: AsyncMock | None = None,
    session_factory: MagicMock | None = None,
    event_bus=None,
) -> AIAnalysisService:
    return AIAnalysisService(
        result_repo=result_repo or AsyncMock(),
        note_repo=note_repo or AsyncMock(),
        llm_adapter=llm or AsyncMock(),
        session_factory=session_factory or MagicMock(),
        event_bus=event_bus,
    )


# ---------------------------------------------------------------------------
# _parse_sentiment
# ---------------------------------------------------------------------------


class TestParseSentiment:
    def test_returns_none_for_none(self):
        assert _parse_sentiment(None) is None

    def test_valid_sentiment_string(self):
        assert _parse_sentiment("bullish") == SentimentScore.BULLISH

    def test_invalid_sentiment_returns_none(self):
        assert _parse_sentiment("garbage_value") is None

    def test_numeric_value_returns_none(self):
        assert _parse_sentiment(42) is None


# ---------------------------------------------------------------------------
# _parse_confidence
# ---------------------------------------------------------------------------


class TestParseConfidence:
    def test_returns_none_for_none(self):
        assert _parse_confidence(None) is None

    def test_valid_decimal_string(self):
        assert _parse_confidence("0.85") == Decimal("0.85")

    def test_invalid_string_returns_none(self):
        assert _parse_confidence("not_a_number") is None

    def test_empty_string_returns_none(self):
        # InvalidOperation for empty string
        assert _parse_confidence("") is None


# ---------------------------------------------------------------------------
# _extract_data_sources
# ---------------------------------------------------------------------------


class TestExtractDataSources:
    def test_maps_known_context_keys(self):
        request = AnalysisRequest(
            analysis_type=AnalysisType.RISK_ASSESSMENT,
            context={"positions": [], "risk_metrics": {}, "factor_exposures": {}},
        )
        sources = _extract_data_sources(request)
        assert "portfolio_positions" in sources
        assert "risk_engine" in sources
        assert "factor_model" in sources

    def test_instruments_adds_security_master(self):
        request = AnalysisRequest(
            analysis_type=AnalysisType.RISK_ASSESSMENT,
            context={"positions": []},
            instruments=["AAPL"],
        )
        sources = _extract_data_sources(request)
        assert "security_master" in sources

    def test_empty_context_no_instruments_uses_fallback(self):
        request = AnalysisRequest(
            analysis_type=AnalysisType.MARKET_COMMENTARY,
            context={"custom_key": "value"},
        )
        sources = _extract_data_sources(request)
        assert sources == ["market_commentary_context"]

    def test_all_source_map_keys(self):
        keys = [
            "positions", "risk_metrics", "factor_exposures", "market_data",
            "news", "earnings", "filings", "sentiment", "prices", "returns",
        ]
        request = AnalysisRequest(
            analysis_type=AnalysisType.PORTFOLIO_REVIEW,
            context={k: {} for k in keys},
        )
        sources = _extract_data_sources(request)
        expected = [
            "portfolio_positions", "risk_engine", "factor_model",
            "market_data_feed", "news_feed", "earnings_data",
            "sec_filings", "sentiment_feed", "price_history", "return_series",
        ]
        for exp in expected:
            assert exp in sources


# ---------------------------------------------------------------------------
# _record_to_result
# ---------------------------------------------------------------------------


class TestRecordToResult:
    def test_converts_record_to_analysis_result(self):
        record = _make_record_mock(
            request_context={"_data_sources": ["risk_engine"]},
            sentiment="bearish",
        )
        result = _record_to_result(record)

        assert result.summary == "A summary"
        assert result.body == "A body"
        assert result.sentiment == SentimentScore.BEARISH
        assert result.confidence == Decimal("0.75")
        assert result.data_sources == ["risk_engine"]
        assert result.key_points == ["point1"]
        assert result.instruments_mentioned == ["AAPL"]

    def test_handles_none_request_context(self):
        record = _make_record_mock(request_context=None)
        result = _record_to_result(record)
        assert result.data_sources == []

    def test_handles_empty_key_points_and_instruments(self):
        record = _make_record_mock(key_points=None, instruments=None)
        result = _record_to_result(record)
        assert result.key_points == []
        assert result.instruments_mentioned == []


# ---------------------------------------------------------------------------
# _note_record_to_dto
# ---------------------------------------------------------------------------


class TestNoteRecordToDto:
    def test_converts_note_record_to_dto(self):
        record = _make_record_mock(
            analysis_type=AnalysisType.MARKET_COMMENTARY.value,
            tags=["macro", "rates"],
            instruments=["TLT"],
        )
        dto = _note_record_to_dto(record)

        assert dto.title == "A title"
        assert dto.content == "Content body"
        assert dto.analysis_type == AnalysisType.MARKET_COMMENTARY
        assert dto.tags == ["macro", "rates"]
        assert dto.instruments == ["TLT"]

    def test_handles_none_instruments_and_tags(self):
        record = _make_record_mock(instruments=None, tags=None)
        dto = _note_record_to_dto(record)
        assert dto.instruments == []
        assert dto.tags == []


# ---------------------------------------------------------------------------
# Service: get_analysis_history
# ---------------------------------------------------------------------------


class TestGetAnalysisHistory:
    @pytest.mark.asyncio
    async def test_returns_converted_results(self):
        repo = AsyncMock()
        record = _make_record_mock(
            analysis_type=AnalysisType.RISK_ASSESSMENT.value,
            request_context={"_data_sources": ["risk_engine"]},
        )
        repo.list_results.return_value = [record]

        svc = _make_service(result_repo=repo)
        results = await svc.get_analysis_history(
            "alpha", analysis_type=AnalysisType.RISK_ASSESSMENT, limit=10
        )

        assert len(results) == 1
        assert results[0].analysis_type == AnalysisType.RISK_ASSESSMENT
        repo.list_results.assert_awaited_once_with(
            "alpha", analysis_type="risk_assessment", limit=10, session=None
        )

    @pytest.mark.asyncio
    async def test_no_type_filter(self):
        repo = AsyncMock()
        repo.list_results.return_value = []

        svc = _make_service(result_repo=repo)
        results = await svc.get_analysis_history("alpha")

        assert results == []
        repo.list_results.assert_awaited_once_with(
            "alpha", analysis_type=None, limit=50, session=None
        )


# ---------------------------------------------------------------------------
# Service: list_research_notes
# ---------------------------------------------------------------------------


class TestListResearchNotes:
    @pytest.mark.asyncio
    async def test_returns_converted_notes(self):
        repo = AsyncMock()
        record = _make_record_mock(
            analysis_type=AnalysisType.MARKET_COMMENTARY.value,
        )
        repo.list_notes.return_value = [record]

        svc = _make_service(note_repo=repo)
        notes = await svc.list_research_notes("alpha", tags=["macro"], limit=20)

        assert len(notes) == 1
        assert notes[0].title == "A title"
        repo.list_notes.assert_awaited_once_with(
            "alpha", tags=["macro"], limit=20, session=None
        )

    @pytest.mark.asyncio
    async def test_empty_list(self):
        repo = AsyncMock()
        repo.list_notes.return_value = []

        svc = _make_service(note_repo=repo)
        notes = await svc.list_research_notes("alpha")

        assert notes == []
