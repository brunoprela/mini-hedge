"""FastAPI routes for security master — thin orchestrators only."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.security_master.dependencies import get_security_master_service
from app.modules.security_master.interface import AssetClass, Instrument
from app.modules.security_master.security_master_service import SecurityMasterService
from app.shared.auth import Permission, require_permission
from app.shared.database import get_db
from app.shared.errors import NotFoundError
from app.shared.request_context import RequestContext

router = APIRouter(prefix="/instruments", tags=["instruments"])


@router.get("", response_model=list[Instrument])
async def list_instruments(
    asset_class: AssetClass | None = Query(default=None),
    request_context: RequestContext = require_permission(Permission.INSTRUMENTS_READ),
    security_master_service: SecurityMasterService = Depends(get_security_master_service),
    session: AsyncSession = Depends(get_db),
) -> list[Instrument]:
    return await security_master_service.get_all_active(asset_class, session=session)


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
