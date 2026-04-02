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
import structlog
from fastapi import Depends, HTTPException, Request
from jwt import PyJWKClient
from pydantic import BaseModel, ConfigDict

from app.shared.request_context import ActorType, RequestContext, get_request_context

logger = structlog.get_logger()

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
            logger.warning("unknown_role_ignored", role=role_name)
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
    fund_id: str | None = None  # UUID of the fund
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
    fund_id: str | None = None,
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
    if fund_id:
        payload["fund_id"] = fund_id
    if delegated_by:
        payload["delegated_by"] = delegated_by
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(
    token: str,
    *,
    secret: str,
    algorithm: str = "HS256",
) -> TokenClaims:
    """Decode and validate an app-issued JWT. Raises jwt.PyJWTError on failure."""
    payload = jwt.decode(token, secret, algorithms=[algorithm])
    return TokenClaims(
        sub=payload["sub"],
        actor_type=ActorType(payload["actor_type"]),
        fund_slug=payload["fund_slug"],
        fund_id=payload.get("fund_id"),
        roles=payload["roles"],
        exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
        iat=datetime.fromtimestamp(payload["iat"], tz=UTC),
        jti=payload["jti"],
        delegated_by=payload.get("delegated_by"),
    )


# ---------------------------------------------------------------------------
# Keycloak JWKS token validation
# ---------------------------------------------------------------------------


class KeycloakClaims(BaseModel):
    """Decoded Keycloak JWT payload."""

    model_config = ConfigDict(frozen=True)

    sub: str  # Keycloak user ID (UUID)
    email: str
    name: str = ""
    email_verified: bool = False


_jwk_client: PyJWKClient | None = None


def get_jwk_client(keycloak_url: str, realm: str) -> PyJWKClient:
    """Get or create a cached PyJWKClient for the Keycloak realm."""
    global _jwk_client
    if _jwk_client is None:
        jwks_url = f"{keycloak_url}/realms/{realm}/protocol/openid-connect/certs"
        _jwk_client = PyJWKClient(jwks_url, cache_keys=True)
    return _jwk_client


def decode_keycloak_token(
    token: str,
    *,
    keycloak_url: str,
    realm: str,
    client_id: str,
    keycloak_browser_url: str = "",
) -> KeycloakClaims:
    """Decode and validate a Keycloak-issued JWT using JWKS.

    *keycloak_url* is the server-side URL used to fetch JWKS keys.
    *keycloak_browser_url*, when set, is used for issuer validation
    (Keycloak stamps tokens with the browser-facing URL).

    Raises jwt.PyJWTError on failure (expired, bad signature, wrong audience).
    """
    jwk_client = get_jwk_client(keycloak_url, realm)
    signing_key = jwk_client.get_signing_key_from_jwt(token)
    issuer_base = keycloak_browser_url or keycloak_url
    issuer = f"{issuer_base}/realms/{realm}"

    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=["account", client_id],
        issuer=issuer,
    )

    given = payload.get("given_name", "")
    family = payload.get("family_name", "")
    name = f"{given} {family}".strip() or payload.get("preferred_username", "")

    return KeycloakClaims(
        sub=payload["sub"],
        email=payload.get("email", ""),
        name=name,
        email_verified=payload.get("email_verified", False),
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
