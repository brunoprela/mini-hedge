"""Alternative data integration — public interface and DTOs."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict  # noqa: TC002

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AltDataSource(StrEnum):
    SATELLITE = "satellite"
    WEB_SCRAPING = "web_scraping"
    SOCIAL_MEDIA = "social_media"
    SEC_FILINGS = "sec_filings"
    PATENT_DATA = "patent_data"
    CREDIT_CARD = "credit_card"
    WEATHER = "weather"
    GEOLOCATION = "geolocation"


class DataFrequency(StrEnum):
    REALTIME = "realtime"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class DataQuality(StrEnum):
    RAW = "raw"
    CLEANED = "cleaned"
    VALIDATED = "validated"
    ENRICHED = "enriched"


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


class AltDataFeed(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str
    source: AltDataSource
    frequency: DataFrequency
    description: str
    instruments: list[str]
    quality: DataQuality
    is_active: bool
    last_updated: datetime | None
    record_count: int
    created_at: datetime


class AltDataPoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    feed_id: UUID
    instrument_id: str | None
    timestamp: datetime
    value: Decimal
    metadata: dict[str, Any] = {}


class AltDataSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    feed_id: UUID
    feed_name: str
    source: AltDataSource
    latest_value: Decimal | None
    avg_value: Decimal | None
    min_value: Decimal | None
    max_value: Decimal | None
    data_points: int
    coverage_start: date | None
    coverage_end: date | None


class SentimentDataPoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    instrument_id: str
    source: str
    timestamp: datetime
    sentiment_score: Decimal  # -1 to 1
    volume: int  # number of mentions
    positive_mentions: int
    negative_mentions: int
    neutral_mentions: int
