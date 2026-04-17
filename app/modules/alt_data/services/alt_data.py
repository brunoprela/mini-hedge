"""Alternative data integration service."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog

from app.modules.alt_data.interfaces import (
    AltDataFeed,
    AltDataPoint,
    AltDataSource,
    AltDataSummary,
    DataFrequency,
    DataQuality,
    SentimentDataPoint,
)
from app.modules.alt_data.models.alt_data_feed import AltDataFeedRecord
from app.modules.alt_data.models.alt_data_point import AltDataPointRecord
from app.shared.audit.events import AuditEventType
from app.shared.events import BaseEvent
from app.shared.schema_registry import shared_topic

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.alt_data.repositories import AltDataFeedRepository, AltDataPointRepository
    from app.shared.adapters.alt_data import AltDataProvider
    from app.shared.events import EventBus

logger = structlog.get_logger()


class AltDataService:
    """Manages alternative data feeds and ingestion."""

    def __init__(
        self,
        feed_repo: AltDataFeedRepository,
        point_repo: AltDataPointRepository,
        providers: list[AltDataProvider],
        session_factory: Any,
        event_bus: EventBus | None = None,
    ) -> None:
        self._feed_repo = feed_repo
        self._point_repo = point_repo
        self._providers = providers
        self._session_factory = session_factory
        self._event_bus = event_bus

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
        await self._feed_repo.insert_feed(record, session=session)

        logger.info("alt_data_feed_created", name=name, source=source)

        if self._event_bus:
            await self._event_bus.publish(
                shared_topic("audit"),
                BaseEvent(
                    event_type=AuditEventType.ALT_DATA_FEED_CREATED,
                    data={
                        "feed_id": record.id,
                        "name": name,
                        "source": source.value,
                        "frequency": frequency.value,
                        "instruments": instruments or [],
                    },
                ),
            )

        return self._feed_to_dto(record)

    async def get_feed(
        self,
        feed_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> AltDataFeed | None:
        record = await self._feed_repo.get_feed(feed_id, session=session)
        return self._feed_to_dto(record) if record else None

    async def list_feeds(
        self,
        *,
        source: AltDataSource | None = None,
        session: AsyncSession | None = None,
    ) -> list[AltDataFeed]:
        source_val = source.value if source is not None else None
        records = await self._feed_repo.list_feeds(source=source_val, session=session)
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
                extra_metadata=dp.metadata or None,
            )
            for dp in data_points
        ]
        await self._point_repo.insert_data_points(records, session=session)

        now = datetime.now(UTC)
        feed = await self._feed_repo.get_feed(str(feed_id), session=session)
        new_count = (feed.record_count if feed else 0) + len(records)
        await self._feed_repo.update_feed(
            str(feed_id), last_updated=now, record_count=new_count, session=session
        )

        logger.info("alt_data_ingested", feed_id=str(feed_id), count=len(records))

        if self._event_bus:
            await self._event_bus.publish(
                shared_topic("audit"),
                BaseEvent(
                    event_type=AuditEventType.ALT_DATA_INGESTED,
                    data={
                        "feed_id": str(feed_id),
                        "data_points_ingested": len(records),
                        "total_record_count": new_count,
                    },
                ),
            )

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
        records = await self._point_repo.get_data_points(
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
                metadata=r.extra_metadata or {},
            )
            for r in records
        ]

    async def get_feed_summary(
        self,
        feed_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> AltDataSummary:
        feed = await self._feed_repo.get_feed(str(feed_id), session=session)
        if feed is None:
            msg = f"Feed {feed_id} not found"
            raise ValueError(msg)

        stats = await self._point_repo.get_summary(str(feed_id), session=session)

        coverage_start = stats["coverage_start"]
        coverage_end = stats["coverage_end"]

        return AltDataSummary(
            feed_id=UUID(feed.id),
            feed_name=feed.name,
            source=AltDataSource(feed.source),
            latest_value=(
                Decimal(str(stats["max_value"])) if stats["max_value"] is not None else None
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
