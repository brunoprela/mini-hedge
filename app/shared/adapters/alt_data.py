"""AltDataProvider protocol and alt data value objects."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import date, datetime
    from decimal import Decimal


class AltDataRecord:
    """A single alternative data observation."""

    __slots__ = ("instrument_id", "timestamp", "value", "source", "metadata")

    def __init__(
        self,
        *,
        instrument_id: str | None,
        timestamp: datetime,
        value: Decimal,
        source: str,
        metadata: dict | None = None,
    ) -> None:
        self.instrument_id = instrument_id
        self.timestamp = timestamp
        self.value = value
        self.source = source
        self.metadata = metadata


class SentimentRecord:
    """Sentiment observation for an instrument."""

    __slots__ = (
        "instrument_id",
        "source",
        "timestamp",
        "sentiment_score",
        "volume",
        "positive_mentions",
        "negative_mentions",
        "neutral_mentions",
    )

    def __init__(
        self,
        *,
        instrument_id: str,
        source: str,
        timestamp: datetime,
        sentiment_score: Decimal,
        volume: int,
        positive_mentions: int,
        negative_mentions: int,
        neutral_mentions: int,
    ) -> None:
        self.instrument_id = instrument_id
        self.source = source
        self.timestamp = timestamp
        self.sentiment_score = sentiment_score
        self.volume = volume
        self.positive_mentions = positive_mentions
        self.negative_mentions = negative_mentions
        self.neutral_mentions = neutral_mentions


class AltDataProvider(Protocol):
    """Vendor-agnostic alternative data source.

    Implementations: file-based (Parquet/CSV), FMP, mock.
    """

    async def fetch_data(
        self, instrument_id: str, start: date, end: date
    ) -> list[AltDataRecord]: ...

    async def get_sentiment(self, instrument_id: str, as_of: date) -> SentimentRecord | None: ...

    @property
    def source_name(self) -> str: ...
