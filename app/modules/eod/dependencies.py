"""FastAPI dependency wrappers for the EOD module."""

from fastapi import HTTPException, Request

from app.modules.eod.escalation import EscalationPolicy
from app.modules.eod.orchestrator import EODOrchestrator
from app.modules.eod.repository import ReconciliationBreakRepository, ReconciliationRepository


def get_eod_orchestrator(request: Request) -> EODOrchestrator:
    orchestrator: EODOrchestrator | None = getattr(request.app.state, "eod_orchestrator", None)
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="EOD module not initialized")
    return orchestrator


def get_recon_repo(request: Request) -> ReconciliationRepository:
    repo: ReconciliationRepository | None = getattr(request.app.state, "recon_repo", None)
    if repo is None:
        raise HTTPException(status_code=503, detail="Reconciliation module not initialized")
    return repo


def get_break_repo(request: Request) -> ReconciliationBreakRepository:
    repo: ReconciliationBreakRepository | None = getattr(request.app.state, "break_repo", None)
    if repo is None:
        raise HTTPException(status_code=503, detail="Reconciliation module not initialized")
    return repo


def get_escalation_policy(request: Request) -> EscalationPolicy:
    policy: EscalationPolicy | None = getattr(request.app.state, "escalation_policy", None)
    if policy is None:
        # Return a default policy if none is explicitly configured
        return EscalationPolicy()
    return policy
