"""AI analysis public interface — DTOs and enums."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AnalysisType(StrEnum):
    MARKET_COMMENTARY = "market_commentary"
    PORTFOLIO_REVIEW = "portfolio_review"
    RISK_ASSESSMENT = "risk_assessment"
    TRADE_RATIONALE = "trade_rationale"
    EARNINGS_SUMMARY = "earnings_summary"
    NEWS_DIGEST = "news_digest"
    FACTOR_COMMENTARY = "factor_commentary"


class SentimentScore(StrEnum):
    VERY_BEARISH = "very_bearish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    BULLISH = "bullish"
    VERY_BULLISH = "very_bullish"


# ---------------------------------------------------------------------------
# Request / Response DTOs
# ---------------------------------------------------------------------------


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    analysis_type: AnalysisType
    context: dict[str, Any]  # flexible input data
    instruments: list[str] = []  # relevant instrument_ids


class AnalysisResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    analysis_type: AnalysisType
    summary: str
    body: str
    sentiment: SentimentScore | None = None
    confidence: Decimal | None = None
    key_points: list[str] = []
    instruments_mentioned: list[str] = []
    data_sources: list[str] = []
    model_used: str
    tokens_used: int
    created_at: datetime


class SentimentAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)

    instrument_id: str
    sentiment: SentimentScore
    confidence: Decimal
    reasoning: str
    news_count: int
    analyzed_at: datetime


class PortfolioInsight(BaseModel):
    model_config = ConfigDict(frozen=True)

    insight_type: str  # "concentration_risk", "sector_drift", "factor_tilt", etc.
    severity: str  # "info", "warning", "critical"
    title: str
    description: str
    affected_instruments: list[str] = []
    suggested_action: str | None = None


class ResearchNote(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    title: str
    content: str
    analysis_type: AnalysisType
    instruments: list[str] = []
    tags: list[str] = []
    created_at: datetime
