"""FastAPI routes for security master — thin orchestrators only."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.security_master.dependencies import get_security_master_service
from app.modules.security_master.interface import AssetClass, Instrument
from app.modules.security_master.service import SecurityMasterService
from app.shared.auth import Permission, require_permission
from app.shared.errors import NotFoundError
from app.shared.request_context import RequestContext

router = APIRouter(prefix="/instruments", tags=["instruments"])


@router.get("", response_model=list[Instrument])
async def list_instruments(
    asset_class: AssetClass | None = Query(default=None),
    ctx: RequestContext = require_permission(Permission.INSTRUMENTS_READ),
    service: SecurityMasterService = Depends(get_security_master_service),
) -> list[Instrument]:
    return await service.get_all_active(asset_class)


@router.get("/search", response_model=list[Instrument])
async def search_instruments(
    q: str = Query(min_length=1),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    ctx: RequestContext = require_permission(Permission.INSTRUMENTS_READ),
    service: SecurityMasterService = Depends(get_security_master_service),
) -> list[Instrument]:
    return await service.search(q, limit, offset=offset)


@router.get("/{instrument_id}", response_model=Instrument)
async def get_instrument(
    instrument_id: UUID,
    ctx: RequestContext = require_permission(Permission.INSTRUMENTS_READ),
    service: SecurityMasterService = Depends(get_security_master_service),
) -> Instrument:
    try:
        return await service.get_by_id(instrument_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
