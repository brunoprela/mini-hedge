"""FastAPI routes for alternative data integration."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from app.modules.alt_data.dependencies import get_alt_data_service
from app.modules.alt_data.interfaces import (
    AltDataFeed,
    AltDataPoint,
    AltDataSource,
    AltDataSummary,
    DataFrequency,
    SentimentDataPoint,
)
from app.modules.alt_data.services import AltDataService
from app.shared.auth import Permission, require_permission
from app.shared.database import get_db, get_read_db

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.shared.auth.request_context import RequestContext

router = APIRouter(prefix="/alt-data", tags=["alt-data"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CreateFeedRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    source: AltDataSource
    frequency: DataFrequency
    description: str = ""
    instruments: list[str] = []


class IngestRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    data_points: list[AltDataPoint]


class SentimentRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    instrument_ids: list[str]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/feeds", response_model=AltDataFeed)
async def create_feed(
    body: CreateFeedRequest,
    request_context: RequestContext = require_permission(Permission.RISK_WRITE),
    service: AltDataService = Depends(get_alt_data_service),
    session: AsyncSession = Depends(get_db),
) -> AltDataFeed:
    return await service.create_feed(
        name=body.name,
        source=body.source,
        frequency=body.frequency,
        description=body.description,
        instruments=body.instruments,
        session=session,
    )


@router.get("/feeds", response_model=list[AltDataFeed])
async def list_feeds(
    source: AltDataSource | None = Query(default=None),
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: AltDataService = Depends(get_alt_data_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[AltDataFeed]:
    return await service.list_feeds(source=source, session=session)


@router.get("/feeds/{feed_id}", response_model=AltDataFeed)
async def get_feed(
    feed_id: UUID,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: AltDataService = Depends(get_alt_data_service),
    session: AsyncSession = Depends(get_read_db),
) -> AltDataFeed:
    feed = await service._repo.get_feed(str(feed_id), session=session)
    if feed is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Feed not found")
    return AltDataService._feed_to_dto(feed)


@router.get("/feeds/{feed_id}/summary", response_model=AltDataSummary)
async def get_feed_summary(
    feed_id: UUID,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: AltDataService = Depends(get_alt_data_service),
    session: AsyncSession = Depends(get_read_db),
) -> AltDataSummary:
    return await service.get_feed_summary(feed_id, session=session)


@router.post("/feeds/{feed_id}/ingest")
async def ingest_data(
    feed_id: UUID,
    body: IngestRequest,
    request_context: RequestContext = require_permission(Permission.RISK_WRITE),
    service: AltDataService = Depends(get_alt_data_service),
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    count = await service.ingest_data(feed_id, body.data_points, session=session)
    return {"ingested": count}


@router.get("/feeds/{feed_id}/data", response_model=list[AltDataPoint])
async def get_feed_data(
    feed_id: UUID,
    instrument_id: str | None = Query(default=None),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: AltDataService = Depends(get_alt_data_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[AltDataPoint]:
    return await service.get_feed_data(
        feed_id, instrument_id=instrument_id, start=start, end=end, session=session
    )


@router.post("/sentiment", response_model=list[SentimentDataPoint])
async def collect_sentiment(
    body: SentimentRequest,
    request_context: RequestContext = require_permission(Permission.RISK_READ),
    service: AltDataService = Depends(get_alt_data_service),
    session: AsyncSession = Depends(get_read_db),
) -> list[SentimentDataPoint]:
    return await service.collect_sentiment(body.instrument_ids, session=session)
