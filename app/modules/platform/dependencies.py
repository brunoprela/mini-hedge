"""FastAPI dependency wrappers for the platform module."""

from fastapi import HTTPException, Request

from app.modules.platform.admin_service import AdminService
from app.modules.platform.audit_repository import AuditLogRepository
from app.modules.platform.audit_verifier import AuditIntegrityVerifier
from app.modules.platform.auth_service import AuthService
from app.modules.platform.portfolio_repository import PortfolioRepository


def get_auth_service(request: Request) -> AuthService:
    service: AuthService | None = getattr(request.app.state, "auth_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="AuthService not initialized")
    return service


def get_portfolio_repo(request: Request) -> PortfolioRepository:
    repo: PortfolioRepository | None = getattr(request.app.state, "portfolio_repo", None)
    if repo is None:
        raise HTTPException(status_code=503, detail="PortfolioRepository not initialized")
    return repo


def get_admin_service(request: Request) -> AdminService:
    service: AdminService | None = getattr(request.app.state, "admin_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="AdminService not initialized")
    return service


def get_audit_repo(request: Request) -> AuditLogRepository:
    repo: AuditLogRepository | None = getattr(request.app.state, "audit_repo", None)
    if repo is None:
        raise HTTPException(status_code=503, detail="AuditLogRepository not initialized")
    return repo


def get_audit_verifier(request: Request) -> AuditIntegrityVerifier:
    verifier: AuditIntegrityVerifier | None = getattr(request.app.state, "audit_verifier", None)
    if verifier is None:
        raise HTTPException(status_code=503, detail="AuditIntegrityVerifier not initialized")
    return verifier
