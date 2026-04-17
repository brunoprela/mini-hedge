"""Financial Modeling Prep alternative data provider.

Provides: social sentiment, analyst estimates, insider trading,
institutional holdings, ESG scores.

API docs: https://financialmodelingprep.com/developer/docs
Requires FMP_API_KEY environment variable.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.shared.adapters.alt_data import AltDataRecord, SentimentRecord

logger = structlog.get_logger()


class FMPAltDataProvider:
    """Alternative data from the Financial Modeling Prep REST API."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://financialmodelingprep.com/api/v3",
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    @property
    def source_name(self) -> str:
        return "fmp"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_data(self, instrument_id: str, start: date, end: date) -> list[AltDataRecord]:
        """Fetch analyst estimates for an instrument within the date range."""
        import httpx

        from app.shared.adapters.alt_data import AltDataRecord

        records: list[AltDataRecord] = []

        url = f"{self._base_url}/analyst-estimates/{instrument_id}"
        params: dict[str, str] = {"apikey": self._api_key}

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=2.0)) as client:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    logger.warning(
                        "fmp_fetch_failed",
                        url=url,
                        status=resp.status_code,
                    )
                    return records

                for item in resp.json():
                    item_date_str = item.get("date", "")
                    try:
                        item_date = datetime.strptime(item_date_str, "%Y-%m-%d").replace(tzinfo=UTC)
                    except ValueError:
                        continue

                    if item_date.date() < start or item_date.date() > end:
                        continue

                    consensus = item.get("estimatedEpsAvg", item.get("estimatedRevenueAvg", 0))
                    records.append(
                        AltDataRecord(
                            instrument_id=instrument_id,
                            timestamp=item_date,
                            value=Decimal(str(consensus)),
                            source="fmp",
                            metadata={
                                "type": "analyst_estimate",
                                "eps_high": str(item.get("estimatedEpsHigh", "")),
                                "eps_low": str(item.get("estimatedEpsLow", "")),
                                "revenue_avg": str(item.get("estimatedRevenueAvg", "")),
                                "number_analysts": str(
                                    item.get("numberAnalystEstimatedRevenue", "")
                                ),
                            },
                        )
                    )
        except httpx.HTTPError as exc:
            logger.warning("fmp_http_error", error=str(exc))

        return records

    async def get_sentiment(self, instrument_id: str, as_of: date) -> SentimentRecord | None:
        """Fetch social sentiment from FMP for the given instrument."""
        import httpx

        from app.shared.adapters.alt_data import SentimentRecord

        url = f"{self._base_url}/historical/social-sentiment"
        params: dict[str, str | int] = {
            "symbol": instrument_id,
            "apikey": self._api_key,
            "limit": 100,
        }

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=2.0)) as client:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    logger.warning(
                        "fmp_sentiment_failed",
                        status=resp.status_code,
                    )
                    return None

                data = resp.json()
                if not data:
                    return None

                # Find the entry closest to as_of (but not after)
                best = None
                best_date: date | None = None
                for item in data:
                    item_date_str = item.get("date", "")
                    try:
                        item_dt = datetime.strptime(item_date_str[:10], "%Y-%m-%d").date()
                    except ValueError:
                        continue
                    if item_dt > as_of:
                        continue
                    if best_date is None or item_dt > best_date:
                        best_date = item_dt
                        best = item

                if best is None:
                    return None

                ts_str = best.get("date", "")
                try:
                    ts = datetime.strptime(ts_str[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
                except ValueError:
                    ts = datetime(best_date.year, best_date.month, best_date.day, tzinfo=UTC)

                positive = int(best.get("stocktwitsPosts", 0)) + int(best.get("twitterPosts", 0))
                negative = int(best.get("stocktwitsComments", 0)) + int(
                    best.get("twitterComments", 0)
                )
                volume = positive + negative
                sentiment_raw = float(best.get("stocktwitsSentiment", 0)) + float(
                    best.get("twitterSentiment", 0)
                )
                # Normalise to -1..1 range
                sentiment_score = max(-1.0, min(1.0, sentiment_raw / 2))

                return SentimentRecord(
                    instrument_id=instrument_id,
                    source="fmp",
                    timestamp=ts,
                    sentiment_score=Decimal(str(round(sentiment_score, 4))),
                    volume=volume,
                    positive_mentions=positive,
                    negative_mentions=negative,
                    neutral_mentions=0,
                )
        except httpx.HTTPError as exc:
            logger.warning("fmp_sentiment_http_error", error=str(exc))
            return None
