"""FastAPI routes for security master — thin orchestrators only."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from app.modules.security_master.interface import AssetClass, Instrument
from app.modules.security_master.service import SecurityMasterService
from app.shared.auth import Permission, require_permission
from app.shared.errors import NotFoundError
from app.shared.request_context import RequestContext

router = APIRouter(prefix="/instruments", tags=["instruments"])


def _get_service(request: Request) -> SecurityMasterService:
    svc = getattr(request.app.state, "security_master_service", None)
    service: SecurityMasterService | None = svc
    if service is None:
        raise HTTPException(status_code=503, detail="SecurityMasterService not initialized")
    return service


@router.get("", response_model=list[Instrument])
async def list_instruments(
    request: Request,
    asset_class: AssetClass | None = Query(default=None),
    ctx: RequestContext = require_permission(Permission.INSTRUMENTS_READ),
) -> list[Instrument]:
    return await _get_service(request).get_all_active(asset_class)


@router.get("/search", response_model=list[Instrument])
async def search_instruments(
    request: Request,
    q: str = Query(min_length=1),
    limit: int = Query(default=20, le=100),
    ctx: RequestContext = require_permission(Permission.INSTRUMENTS_READ),
) -> list[Instrument]:
    return await _get_service(request).search(q, limit)


@router.get("/{instrument_id}", response_model=Instrument)
async def get_instrument(
    request: Request,
    instrument_id: UUID,
    ctx: RequestContext = require_permission(Permission.INSTRUMENTS_READ),
) -> Instrument:
    try:
        return await _get_service(request).get_by_id(instrument_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
