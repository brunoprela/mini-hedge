"""FastAPI routes for security master — thin orchestrators only."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.security_master.dependencies import get_security_master_service
from app.modules.security_master.interfaces import AssetClass, Instrument
from app.modules.security_master.services import SecurityMasterService
from app.shared.auth import Permission, require_permission
from app.shared.auth.request_context import RequestContext
from app.shared.database import get_db
from app.shared.errors import NotFoundError

router = APIRouter(prefix="/instruments", tags=["instruments"])


class CreateInstrumentRequest(BaseModel):
    name: str
    ticker: str
    asset_class: AssetClass
    currency: str
    exchange: str
    country: str
    sector: str | None = None
    industry: str | None = None


class UpdateInstrumentRequest(BaseModel):
    name: str | None = None
    ticker: str | None = None
    currency: str | None = None
    exchange: str | None = None
    country: str | None = None
    sector: str | None = None
    industry: str | None = None


@router.get("", response_model=list[Instrument])
async def list_instruments(
    asset_class: AssetClass | None = Query(default=None),
    request_context: RequestContext = require_permission(Permission.INSTRUMENTS_READ),
    security_master_service: SecurityMasterService = Depends(get_security_master_service),
    session: AsyncSession = Depends(get_db),
) -> list[Instrument]:
    return await security_master_service.list_active(asset_class, session=session)


@router.get("/search", response_model=list[Instrument])
async def search_instruments(
    q: str = Query(min_length=1),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    request_context: RequestContext = require_permission(Permission.INSTRUMENTS_READ),
    security_master_service: SecurityMasterService = Depends(get_security_master_service),
    session: AsyncSession = Depends(get_db),
) -> list[Instrument]:
    return await security_master_service.search(q, limit, offset=offset, session=session)


@router.get("/{instrument_id}", response_model=Instrument)
async def get_instrument(
    instrument_id: UUID,
    request_context: RequestContext = require_permission(Permission.INSTRUMENTS_READ),
    security_master_service: SecurityMasterService = Depends(get_security_master_service),
    session: AsyncSession = Depends(get_db),
) -> Instrument:
    try:
        return await security_master_service.get_by_id(instrument_id, session=session)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e


@router.post("", response_model=Instrument, status_code=201)
async def create_instrument(
    body: CreateInstrumentRequest,
    request_context: RequestContext = require_permission(Permission.INSTRUMENTS_WRITE),
    security_master_service: SecurityMasterService = Depends(get_security_master_service),
    session: AsyncSession = Depends(get_db),
) -> Instrument:
    return await security_master_service.create_instrument(
        name=body.name,
        ticker=body.ticker,
        asset_class=body.asset_class,
        currency=body.currency,
        exchange=body.exchange,
        country=body.country,
        sector=body.sector,
        industry=body.industry,
        session=session,
    )


@router.patch("/{instrument_id}", response_model=Instrument)
async def update_instrument(
    instrument_id: UUID,
    body: UpdateInstrumentRequest,
    request_context: RequestContext = require_permission(Permission.INSTRUMENTS_WRITE),
    security_master_service: SecurityMasterService = Depends(get_security_master_service),
    session: AsyncSession = Depends(get_db),
) -> Instrument:
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        return await security_master_service.update_instrument(
            instrument_id, updates, session=session
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
