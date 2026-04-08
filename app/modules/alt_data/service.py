"""Alternative data integration service."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog

from app.modules.alt_data.interface import (
    AltDataFeed,
    AltDataPoint,
    AltDataSource,
    AltDataSummary,
    DataFrequency,
    DataQuality,
    SentimentDataPoint,
)
from app.modules.alt_data.models import AltDataFeedRecord, AltDataPointRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.alt_data.repository import AltDataRepository
    from app.shared.adapters import AltDataProvider

logger = structlog.get_logger()


class AltDataService:
    """Manages alternative data feeds and ingestion."""

    def __init__(
        self,
        repo: AltDataRepository,
        providers: list[AltDataProvider],
        session_factory: Any,
    ) -> None:
        self._repo = repo
        self._providers = providers
        self._session_factory = session_factory

    async def create_feed(
        self,
        name: str,
        source: AltDataSource,
        frequency: DataFrequency,
        description: str | None = None,
        instruments: list[str] | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> AltDataFeed:
        record = AltDataFeedRecord(
            name=name,
            source=source.value,
            frequency=frequency.value,
            description=description or "",
            instruments=instruments or [],
            quality=DataQuality.RAW.value,
            is_active=True,
            record_count=0,
        )
        await self._repo.create_feed(record, session=session)

        logger.info("alt_data_feed_created", name=name, source=source)
        return self._feed_to_dto(record)

    async def list_feeds(
        self,
        *,
        source: AltDataSource | None = None,
        session: AsyncSession | None = None,
    ) -> list[AltDataFeed]:
        source_val = source.value if source is not None else None
        records = await self._repo.list_feeds(source=source_val, session=session)
        return [self._feed_to_dto(r) for r in records]

    async def ingest_data(
        self,
        feed_id: UUID,
        data_points: list[AltDataPoint],
        *,
        session: AsyncSession | None = None,
    ) -> int:
        records = [
            AltDataPointRecord(
                feed_id=str(feed_id),
                instrument_id=dp.instrument_id,
                timestamp=dp.timestamp,
                value=dp.value,
                metadata=dp.metadata or None,
            )
            for dp in data_points
        ]
        await self._repo.insert_data_points(records, session=session)

        now = datetime.now(UTC)
        feed = await self._repo.get_feed(str(feed_id), session=session)
        new_count = (feed.record_count if feed else 0) + len(records)
        await self._repo.update_feed(
            str(feed_id), last_updated=now, record_count=new_count, session=session
        )

        logger.info("alt_data_ingested", feed_id=str(feed_id), count=len(records))
        return len(records)

    async def get_feed_data(
        self,
        feed_id: UUID,
        *,
        instrument_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        session: AsyncSession | None = None,
    ) -> list[AltDataPoint]:
        records = await self._repo.get_data_points(
            str(feed_id),
            instrument_id=instrument_id,
            start=start,
            end=end,
            session=session,
        )
        return [
            AltDataPoint(
                feed_id=UUID(r.feed_id),
                instrument_id=r.instrument_id,
                timestamp=r.timestamp,
                value=r.value,
                metadata=r.metadata or {},
            )
            for r in records
        ]

    async def get_feed_summary(
        self,
        feed_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> AltDataSummary:
        feed = await self._repo.get_feed(str(feed_id), session=session)
        if feed is None:
            msg = f"Feed {feed_id} not found"
            raise ValueError(msg)

        stats = await self._repo.get_summary(str(feed_id), session=session)

        coverage_start = stats["coverage_start"]
        coverage_end = stats["coverage_end"]

        return AltDataSummary(
            feed_id=UUID(feed.id),
            feed_name=feed.name,
            source=AltDataSource(feed.source),
            latest_value=(
                Decimal(str(stats["max_value"]))
                if stats["max_value"] is not None
                else None
            ),
            avg_value=Decimal(str(stats["avg_value"])) if stats["avg_value"] is not None else None,
            min_value=Decimal(str(stats["min_value"])) if stats["min_value"] is not None else None,
            max_value=Decimal(str(stats["max_value"])) if stats["max_value"] is not None else None,
            data_points=stats["data_points"],
            coverage_start=coverage_start.date() if coverage_start else None,
            coverage_end=coverage_end.date() if coverage_end else None,
        )

    async def collect_sentiment(
        self,
        instrument_ids: list[str],
        *,
        session: AsyncSession | None = None,
    ) -> list[SentimentDataPoint]:
        """Collect sentiment from configured providers for instruments."""
        if not self._providers:
            return []

        today = date.today()
        results: list[SentimentDataPoint] = []
        for provider in self._providers:
            for iid in instrument_ids:
                record = await provider.get_sentiment(iid, today)
                if record is None:
                    continue
                results.append(
                    SentimentDataPoint(
                        instrument_id=record.instrument_id,
                        source=record.source,
                        timestamp=record.timestamp,
                        sentiment_score=record.sentiment_score,
                        volume=record.volume,
                        positive_mentions=record.positive_mentions,
                        negative_mentions=record.negative_mentions,
                        neutral_mentions=record.neutral_mentions,
                    )
                )

        logger.info("sentiment_collected", count=len(results))
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _feed_to_dto(record: AltDataFeedRecord) -> AltDataFeed:
        return AltDataFeed(
            id=UUID(record.id),
            name=record.name,
            source=AltDataSource(record.source),
            frequency=DataFrequency(record.frequency),
            description=record.description or "",
            instruments=record.instruments or [],
            quality=DataQuality(record.quality),
            is_active=record.is_active,
            last_updated=record.last_updated,
            record_count=record.record_count,
            created_at=record.created_at,
        )
