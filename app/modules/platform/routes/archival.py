"""Admin API routes — audit archival endpoints."""

from typing import Any

from fastapi import APIRouter, Depends

from app.modules.platform.dependencies import get_archival_service
from app.shared.audit.archival_service import ArchivalService
from app.shared.auth import Permission, require_platform_permission
from app.shared.auth.request_context import RequestContext

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/archival")
async def list_archives(
    fund_slug: str | None = None,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_AUDIT_READ),
    archival_service: ArchivalService = Depends(get_archival_service),
) -> list[dict[str, Any]]:
    """List all archived audit months, optionally filtered by fund."""
    return await archival_service.list_archives(fund_slug=fund_slug)


@router.post("/archival/run")
async def run_archival(
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_AUDIT_READ),
    archival_service: ArchivalService = Depends(get_archival_service),
) -> dict[str, Any]:
    """Trigger archival of all eligible months across all active funds."""
    results = await archival_service.run_archival()
    return {
        "months_archived": len(results),
        "total_records": sum(r.records_archived for r in results),
        "archives": [
            {
                "object_key": r.object_key,
                "records_archived": r.records_archived,
                "size_bytes": r.size_bytes,
            }
            for r in results
        ],
    }


@router.post("/archival/{fund_slug}/{year}/{month}")
async def archive_fund_month(
    fund_slug: str,
    year: int,
    month: int,
    request_context: RequestContext = require_platform_permission(Permission.PLATFORM_AUDIT_READ),
    archival_service: ArchivalService = Depends(get_archival_service),
) -> dict[str, Any]:
    """Archive a specific fund/month to cold storage."""
    result = await archival_service.archive_fund_month(fund_slug, year, month)
    if result is None:
        return {"status": "skipped", "reason": "already archived or no records"}
    return {
        "status": "archived",
        "object_key": result.object_key,
        "records_archived": result.records_archived,
        "size_bytes": result.size_bytes,
    }
