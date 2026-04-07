"""FastAPI routes for block trade allocations."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.modules.orders.allocation_interface import (
    BlockAllocationSummary,
    CreateBlockAllocationRequest,
)
from app.modules.orders.allocation_service import AllocationService
from app.shared.auth import Permission, require_permission
from app.shared.request_context import RequestContext

router = APIRouter(prefix="/allocations", tags=["allocations"])


def _get_allocation_service(request: Request) -> AllocationService:
    service: AllocationService | None = getattr(request.app.state, "allocation_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="AllocationService not initialized",
        )
    return service


@router.post("", response_model=BlockAllocationSummary, status_code=201)
async def create_block_allocation(
    body: CreateBlockAllocationRequest,
    request_context: RequestContext = require_permission(Permission.ORDERS_CREATE),
    allocation_service: AllocationService = Depends(_get_allocation_service),
) -> BlockAllocationSummary:
    try:
        return await allocation_service.create_block_allocation(
            request=body,
            actor_id=request_context.actor_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{allocation_id}", response_model=BlockAllocationSummary)
async def get_allocation(
    allocation_id: UUID,
    request_context: RequestContext = require_permission(Permission.ORDERS_READ),
    allocation_service: AllocationService = Depends(_get_allocation_service),
) -> BlockAllocationSummary:
    try:
        return await allocation_service.get_allocation(allocation_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{allocation_id}/cancel", response_model=BlockAllocationSummary)
async def cancel_allocation(
    allocation_id: UUID,
    request_context: RequestContext = require_permission(Permission.ORDERS_CANCEL),
    allocation_service: AllocationService = Depends(_get_allocation_service),
) -> BlockAllocationSummary:
    try:
        return await allocation_service.cancel_allocation(
            allocation_id, actor_id=request_context.actor_id
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
