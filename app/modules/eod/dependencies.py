"""FastAPI dependency wrappers for the EOD module."""

from fastapi import HTTPException, Request

from app.modules.eod.orchestrator import EODOrchestrator


def get_eod_orchestrator(request: Request) -> EODOrchestrator:
    orchestrator: EODOrchestrator | None = getattr(request.app.state, "eod_orchestrator", None)
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="EOD module not initialized")
    return orchestrator
