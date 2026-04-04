"""RBAC definitions and FastAPI authentication dependencies.

This module provides:
- Role and Permission enums with a static RBAC mapping
- FastAPI dependencies for permission checking

JWT encode/decode, Keycloak validation, and API key hashing
live in :mod:`app.shared.jwt` to keep the shared kernel focused.
Symbols are re-exported here for backwards compatibility.
"""

from __future__ import annotations

from enum import StrEnum

import structlog
from fastapi import Depends, HTTPException, Request

from app.shared.jwt import (
    KeycloakClaims,
    TokenClaims,
    decode_keycloak_token,
    decode_token,
    encode_token,
    generate_api_key,
    hash_api_key,
)
from app.shared.request_context import ActorType, RequestContext, get_request_context

# Re-export JWT symbols so existing `from app.shared.auth import ...` still works.
__all__ = [
    "FGA_FUND_PERMISSIONS",
    "FGA_PERMISSION_MAP",
    "KeycloakClaims",
    "PERMISSION_TO_FGA",
    "PLATFORM_ROLE_PERMISSIONS",
    "Permission",
    "PlatformRole",
    "Role",
    "ROLE_PERMISSIONS",
    "TokenClaims",
    "decode_keycloak_token",
    "decode_token",
    "encode_token",
    "generate_api_key",
    "get_actor_context",
    "hash_api_key",
    "require_permission",
    "require_platform_permission",
    "resolve_permissions",
]

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# RBAC: Roles and Permissions
# ---------------------------------------------------------------------------


class Role(StrEnum):
    ADMIN = "admin"
    PORTFOLIO_MANAGER = "portfolio_manager"
    ANALYST = "analyst"
    RISK_MANAGER = "risk_manager"
    COMPLIANCE_OFFICER = "compliance_officer"
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

    # Phase 2: Orders
    ORDERS_READ = "orders:read"
    ORDERS_CREATE = "orders:create"
    ORDERS_CANCEL = "orders:cancel"

    # Phase 2: Compliance
    COMPLIANCE_READ = "compliance:read"
    COMPLIANCE_WRITE = "compliance:write"

    # Phase 2: Exposure
    EXPOSURE_READ = "exposure:read"

    # Phase 3: Risk
    RISK_READ = "risk:read"

    # Phase 3: Cash Management
    CASH_READ = "cash:read"
    CASH_WRITE = "cash:write"

    # Phase 3: Performance Attribution
    ATTRIBUTION_READ = "attribution:read"

    # Phase 3: Alpha Engine
    ALPHA_READ = "alpha:read"
    ALPHA_WRITE = "alpha:write"

    # Platform-level permissions (for operators)
    PLATFORM_USERS_READ = "platform:users.read"
    PLATFORM_USERS_WRITE = "platform:users.write"
    PLATFORM_FUNDS_READ = "platform:funds.read"
    PLATFORM_FUNDS_WRITE = "platform:funds.write"
    PLATFORM_OPERATORS_READ = "platform:operators.read"
    PLATFORM_OPERATORS_WRITE = "platform:operators.write"
    PLATFORM_AUDIT_READ = "platform:audit.read"
    PLATFORM_ACCESS_READ = "platform:access.read"
    PLATFORM_ACCESS_WRITE = "platform:access.write"


class PlatformRole(StrEnum):
    OPS_ADMIN = "ops_admin"
    OPS_VIEWER = "ops_viewer"


PLATFORM_ROLE_PERMISSIONS: dict[PlatformRole, frozenset[Permission]] = {
    PlatformRole.OPS_ADMIN: frozenset(
        {
            Permission.PLATFORM_USERS_READ,
            Permission.PLATFORM_USERS_WRITE,
            Permission.PLATFORM_FUNDS_READ,
            Permission.PLATFORM_FUNDS_WRITE,
            Permission.PLATFORM_OPERATORS_READ,
            Permission.PLATFORM_OPERATORS_WRITE,
            Permission.PLATFORM_AUDIT_READ,
            Permission.PLATFORM_ACCESS_READ,
            Permission.PLATFORM_ACCESS_WRITE,
        }
    ),
    PlatformRole.OPS_VIEWER: frozenset(
        {
            Permission.PLATFORM_USERS_READ,
            Permission.PLATFORM_FUNDS_READ,
            Permission.PLATFORM_OPERATORS_READ,
            Permission.PLATFORM_AUDIT_READ,
            Permission.PLATFORM_ACCESS_READ,
        }
    ),
}


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(
        {
            Permission.INSTRUMENTS_READ,
            Permission.INSTRUMENTS_WRITE,
            Permission.PRICES_READ,
            Permission.POSITIONS_READ,
            Permission.POSITIONS_WRITE,
            Permission.TRADES_EXECUTE,
            Permission.FUNDS_READ,
            Permission.FUNDS_MANAGE,
            Permission.ORDERS_READ,
            Permission.ORDERS_CREATE,
            Permission.ORDERS_CANCEL,
            Permission.COMPLIANCE_READ,
            Permission.COMPLIANCE_WRITE,
            Permission.EXPOSURE_READ,
            Permission.RISK_READ,
            Permission.CASH_READ,
            Permission.CASH_WRITE,
            Permission.ATTRIBUTION_READ,
            Permission.ALPHA_READ,
            Permission.ALPHA_WRITE,
        }
    ),
    Role.PORTFOLIO_MANAGER: frozenset(
        {
            Permission.INSTRUMENTS_READ,
            Permission.PRICES_READ,
            Permission.POSITIONS_READ,
            Permission.POSITIONS_WRITE,
            Permission.TRADES_EXECUTE,
            Permission.FUNDS_READ,
            Permission.ORDERS_READ,
            Permission.ORDERS_CREATE,
            Permission.ORDERS_CANCEL,
            Permission.COMPLIANCE_READ,
            Permission.EXPOSURE_READ,
            Permission.RISK_READ,
            Permission.CASH_READ,
            Permission.CASH_WRITE,
            Permission.ATTRIBUTION_READ,
            Permission.ALPHA_READ,
            Permission.ALPHA_WRITE,
        }
    ),
    Role.ANALYST: frozenset(
        {
            Permission.INSTRUMENTS_READ,
            Permission.PRICES_READ,
            Permission.POSITIONS_READ,
            Permission.FUNDS_READ,
            Permission.ORDERS_READ,
            Permission.EXPOSURE_READ,
            Permission.RISK_READ,
            Permission.CASH_READ,
            Permission.ATTRIBUTION_READ,
            Permission.ALPHA_READ,
        }
    ),
    Role.RISK_MANAGER: frozenset(
        {
            Permission.INSTRUMENTS_READ,
            Permission.PRICES_READ,
            Permission.POSITIONS_READ,
            Permission.FUNDS_READ,
            Permission.ORDERS_READ,
            Permission.COMPLIANCE_READ,
            Permission.EXPOSURE_READ,
            Permission.RISK_READ,
            Permission.CASH_READ,
            Permission.ATTRIBUTION_READ,
            Permission.ALPHA_READ,
        }
    ),
    Role.COMPLIANCE_OFFICER: frozenset(
        {
            Permission.INSTRUMENTS_READ,
            Permission.PRICES_READ,
            Permission.POSITIONS_READ,
            Permission.FUNDS_READ,
            Permission.ORDERS_READ,
            Permission.COMPLIANCE_READ,
            Permission.COMPLIANCE_WRITE,
            Permission.EXPOSURE_READ,
            Permission.RISK_READ,
            Permission.CASH_READ,
            Permission.ATTRIBUTION_READ,
            Permission.ALPHA_READ,
        }
    ),
    Role.VIEWER: frozenset(
        {
            Permission.INSTRUMENTS_READ,
            Permission.PRICES_READ,
            Permission.POSITIONS_READ,
            Permission.FUNDS_READ,
            Permission.ORDERS_READ,
        }
    ),
}


# FGA permission relation names — these are directly assignable on fund objects
# and also computed from roles via the FGA model.
# This list must match the can_* relations in fga_model.json.
FGA_FUND_PERMISSIONS = [
    "can_read_instruments",
    "can_write_instruments",
    "can_read_prices",
    "can_read_positions",
    "can_write_positions",
    "can_execute_trades",
    "can_read_fund",
    "can_manage_fund",
    "can_read_orders",
    "can_create_orders",
    "can_cancel_orders",
    "can_read_compliance",
    "can_manage_compliance",
    "can_read_exposure",
    "can_read_risk",
    "can_read_cash",
    "can_write_cash",
    "can_read_attribution",
    "can_read_alpha",
    "can_write_alpha",
]

# Map FGA permission relation name → Permission enum value
FGA_PERMISSION_MAP: dict[str, str] = {
    "can_read_instruments": Permission.INSTRUMENTS_READ,
    "can_write_instruments": Permission.INSTRUMENTS_WRITE,
    "can_read_prices": Permission.PRICES_READ,
    "can_read_positions": Permission.POSITIONS_READ,
    "can_write_positions": Permission.POSITIONS_WRITE,
    "can_execute_trades": Permission.TRADES_EXECUTE,
    "can_read_fund": Permission.FUNDS_READ,
    "can_manage_fund": Permission.FUNDS_MANAGE,
    "can_read_orders": Permission.ORDERS_READ,
    "can_create_orders": Permission.ORDERS_CREATE,
    "can_cancel_orders": Permission.ORDERS_CANCEL,
    "can_read_compliance": Permission.COMPLIANCE_READ,
    "can_manage_compliance": Permission.COMPLIANCE_WRITE,
    "can_read_exposure": Permission.EXPOSURE_READ,
    "can_read_risk": Permission.RISK_READ,
    "can_read_cash": Permission.CASH_READ,
    "can_write_cash": Permission.CASH_WRITE,
    "can_read_attribution": Permission.ATTRIBUTION_READ,
    "can_read_alpha": Permission.ALPHA_READ,
    "can_write_alpha": Permission.ALPHA_WRITE,
}

# Reverse map: Permission enum value → FGA relation name
PERMISSION_TO_FGA: dict[str, str] = {v: k for k, v in FGA_PERMISSION_MAP.items()}


def resolve_permissions(roles: frozenset[str]) -> frozenset[str]:
    """Expand a set of role names into the union of their permissions.

    Used for API key and agent token auth where permissions are derived
    from roles stored in the token/record (not from FGA).
    For Keycloak-authenticated users, permissions are resolved directly
    from FGA via list_relations on can_* relations.
    """
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


def require_platform_permission(*perms: Permission):  # type: ignore[no-untyped-def]
    """FastAPI dependency — checks the caller is a platform operator with required perms."""

    async def _check(
        ctx: RequestContext = Depends(get_actor_context),
    ) -> RequestContext:
        if not ctx.is_platform_operator:
            raise HTTPException(status_code=403, detail="Platform operator access required")
        missing = {p.value for p in perms} - set(ctx.permissions)
        if missing:
            raise HTTPException(
                status_code=403,
                detail=f"Missing permissions: {', '.join(sorted(missing))}",
            )
        return ctx

    return Depends(_check)
