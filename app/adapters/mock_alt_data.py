"""Deterministic mock alternative data provider for testing.

Generates repeatable data based on hashing instrument_id + date, so tests
get stable values without any external dependencies.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.shared.adapters.alt_data import AltDataRecord, SentimentRecord


def _deterministic_seed(instrument_id: str, as_of: date) -> int:
    """Return a deterministic integer seed from instrument + date."""
    return hash(instrument_id + str(as_of)) & 0x7FFFFFFF


class MockAltDataProvider:
    """Deterministic mock alternative data provider for testing."""

    @property
    def source_name(self) -> str:
        return "mock"

    async def fetch_data(self, instrument_id: str, start: date, end: date) -> list[AltDataRecord]:
        """Generate deterministic data points based on hash of instrument+date."""
        from app.shared.adapters.alt_data import AltDataRecord

        records: list[AltDataRecord] = []
        one_day = (end - start).days + 1
        for day_offset in range(one_day):
            d = date(
                start.year,
                start.month,
                start.day,
            )
            # Advance by day_offset
            from datetime import timedelta

            d = start + timedelta(days=day_offset)
            if d > end:
                break

            seed = _deterministic_seed(instrument_id, d)
            value = Decimal(str(round(seed % 10001 / 100, 2)))
            records.append(
                AltDataRecord(
                    instrument_id=instrument_id,
                    timestamp=datetime(d.year, d.month, d.day, tzinfo=UTC),
                    value=value,
                    source="mock",
                )
            )

        return records

    async def get_sentiment(self, instrument_id: str, as_of: date) -> SentimentRecord | None:
        """Generate deterministic sentiment based on hash."""
        from app.shared.adapters.alt_data import SentimentRecord

        seed = _deterministic_seed(instrument_id, as_of)
        score = Decimal(str(round((seed % 2001 - 1000) / 1000, 4)))
        volume = 50 + (seed % 951)  # 50-1000
        positive = int(volume * max(0, float(score + 1) / 2))
        negative = int(volume * max(0, float(1 - score) / 2))
        neutral = volume - positive - negative

        return SentimentRecord(
            instrument_id=instrument_id,
            source="mock",
            timestamp=datetime(as_of.year, as_of.month, as_of.day, tzinfo=UTC),
            sentiment_score=score,
            volume=volume,
            positive_mentions=positive,
            negative_mentions=negative,
            neutral_mentions=max(0, neutral),
        )
