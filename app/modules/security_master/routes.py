"""FastAPI routes for security master — thin orchestrators only."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.modules.security_master.interface import AssetClass, Instrument
from app.modules.security_master.service import SecurityMasterService
from app.shared.auth import Permission, require_permission
from app.shared.errors import NotFoundError
from app.shared.request_context import RequestContext

router = APIRouter(prefix="/instruments", tags=["instruments"])

# Service injected at app startup via router state
_service: SecurityMasterService | None = None


def init_routes(service: SecurityMasterService) -> None:
    global _service
    _service = service


def _get_service() -> SecurityMasterService:
    assert _service is not None, "SecurityMasterService not initialized"
    return _service


@router.get("", response_model=list[Instrument])
async def list_instruments(
    asset_class: AssetClass | None = Query(default=None),
    ctx: RequestContext = require_permission(Permission.INSTRUMENTS_READ),
) -> list[Instrument]:
    return await _get_service().get_all_active(asset_class)


@router.get("/search", response_model=list[Instrument])
async def search_instruments(
    q: str = Query(min_length=1),
    limit: int = Query(default=20, le=100),
    ctx: RequestContext = require_permission(Permission.INSTRUMENTS_READ),
) -> list[Instrument]:
    return await _get_service().search(q, limit)


@router.get("/{instrument_id}", response_model=Instrument)
async def get_instrument(
    instrument_id: UUID,
    ctx: RequestContext = require_permission(Permission.INSTRUMENTS_READ),
) -> Instrument:
    try:
        return await _get_service().get_by_id(instrument_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e
