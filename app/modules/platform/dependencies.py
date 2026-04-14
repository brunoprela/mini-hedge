"""FastAPI dependency wrappers for the platform module."""

from fastapi import HTTPException, Request

from app.modules.platform.core.audit_verifier import AuditIntegrityVerifier
from app.modules.platform.repositories import AuditLogRepository, PortfolioRepository
from app.modules.platform.repositories.api_key import APIKeyRepository
from app.modules.platform.services import AdminService, AuthService
from app.shared.audit.archival_service import ArchivalService


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


def get_api_key_repo(request: Request) -> APIKeyRepository:
    repo: APIKeyRepository | None = getattr(request.app.state, "api_key_repo", None)
    if repo is None:
        raise HTTPException(status_code=503, detail="APIKeyRepository not initialized")
    return repo


def get_archival_service(request: Request) -> ArchivalService:
    service: ArchivalService | None = getattr(request.app.state, "archival_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="ArchivalService not initialized")
    return service
