"""Authentication and authorization — JWT, RBAC, permission enforcement.

This module provides:
- Role and Permission enums with a static RBAC mapping
- JWT encode/decode using HS256
- FastAPI dependencies for permission checking
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import uuid4

import jwt
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from app.shared.request_context import ActorType, RequestContext, get_request_context

# ---------------------------------------------------------------------------
# RBAC: Roles and Permissions
# ---------------------------------------------------------------------------


class Role(StrEnum):
    ADMIN = "admin"
    PORTFOLIO_MANAGER = "portfolio_manager"
    ANALYST = "analyst"
    RISK_MANAGER = "risk_manager"
    COMPLIANCE = "compliance"
    VIEWER = "viewer"


class Permission(StrEnum):
    INSTRUMENTS_READ = "instruments:read"
    INSTRUMENTS_WRITE = "instruments:write"
    PRICES_READ = "prices:read"
    POSITIONS_READ = "positions:read"
    POSITIONS_WRITE = "positions:write"
    TRADES_EXECUTE = "trades:execute"
    FUNDS_READ = "funds:read"
    FUNDS_MANAGE = "funds:manage"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.PORTFOLIO_MANAGER: frozenset(
        {
            Permission.INSTRUMENTS_READ,
            Permission.PRICES_READ,
            Permission.POSITIONS_READ,
            Permission.POSITIONS_WRITE,
            Permission.TRADES_EXECUTE,
            Permission.FUNDS_READ,
        }
    ),
    Role.ANALYST: frozenset(
        {
            Permission.INSTRUMENTS_READ,
            Permission.PRICES_READ,
            Permission.POSITIONS_READ,
            Permission.FUNDS_READ,
        }
    ),
    Role.RISK_MANAGER: frozenset(
        {
            Permission.INSTRUMENTS_READ,
            Permission.PRICES_READ,
            Permission.POSITIONS_READ,
            Permission.FUNDS_READ,
        }
    ),
    Role.COMPLIANCE: frozenset(
        {
            Permission.INSTRUMENTS_READ,
            Permission.PRICES_READ,
            Permission.POSITIONS_READ,
            Permission.FUNDS_READ,
        }
    ),
    Role.VIEWER: frozenset(
        {
            Permission.INSTRUMENTS_READ,
            Permission.PRICES_READ,
            Permission.POSITIONS_READ,
            Permission.FUNDS_READ,
        }
    ),
}


def resolve_permissions(roles: frozenset[str]) -> frozenset[str]:
    """Expand a set of role names into the union of their permissions."""
    perms: set[str] = set()
    for role_name in roles:
        try:
            role = Role(role_name)
        except ValueError:
            continue
        perms |= ROLE_PERMISSIONS.get(role, frozenset())
    return frozenset(perms)


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------


class TokenClaims(BaseModel):
    """Decoded JWT payload."""

    model_config = ConfigDict(frozen=True)

    sub: str  # actor ID
    actor_type: ActorType
    fund_slug: str
    roles: list[str]
    exp: datetime
    iat: datetime
    jti: str
    delegated_by: str | None = None


def encode_token(
    *,
    actor_id: str,
    actor_type: ActorType,
    fund_slug: str,
    roles: list[str],
    secret: str,
    algorithm: str = "HS256",
    expiry_minutes: int = 60,
    delegated_by: str | None = None,
) -> str:
    """Create a signed JWT."""
    now = datetime.now(UTC)
    payload = {
        "sub": actor_id,
        "actor_type": actor_type.value,
        "fund_slug": fund_slug,
        "roles": roles,
        "iat": now,
        "exp": now + timedelta(minutes=expiry_minutes),
        "jti": str(uuid4()),
    }
    if delegated_by:
        payload["delegated_by"] = delegated_by
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(
    token: str,
    *,
    secret: str,
    algorithm: str = "HS256",
) -> TokenClaims:
    """Decode and validate a JWT. Raises jwt.PyJWTError on failure."""
    payload = jwt.decode(token, secret, algorithms=[algorithm])
    return TokenClaims(
        sub=payload["sub"],
        actor_type=ActorType(payload["actor_type"]),
        fund_slug=payload["fund_slug"],
        roles=payload["roles"],
        exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
        iat=datetime.fromtimestamp(payload["iat"], tz=UTC),
        jti=payload["jti"],
        delegated_by=payload.get("delegated_by"),
    )


# ---------------------------------------------------------------------------
# API key hashing
# ---------------------------------------------------------------------------


def hash_api_key(raw_key: str) -> str:
    """SHA-256 hash of a raw API key for storage."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a random API key with 'mh_' prefix."""
    return f"mh_{uuid4().hex}"


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


def get_actor_context(request: Request) -> RequestContext:
    """FastAPI dependency — returns the authenticated RequestContext.

    Use directly when you need the actor's identity without a specific
    permission check.  Raises 401 if no user is authenticated.
    """
    ctx = get_request_context()
    if ctx.actor_type == ActorType.SYSTEM:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )
    return ctx


def require_permission(*perms: Permission):  # type: ignore[no-untyped-def]
    """FastAPI dependency that checks the caller has all listed permissions."""

    async def _check(
        ctx: RequestContext = Depends(get_actor_context),
    ) -> RequestContext:
        missing = {p.value for p in perms} - set(ctx.permissions)
        if missing:
            raise HTTPException(
                status_code=403,
                detail=f"Missing permissions: {', '.join(sorted(missing))}",
            )
        return ctx

    return Depends(_check)
