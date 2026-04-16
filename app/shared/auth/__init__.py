"""Auth subpackage — re-exports all public symbols for convenience.

Consolidates request_context, jwt, token_revocation, and permissions
(RBAC + FastAPI dependencies) into a single ``app.shared.auth`` namespace.
"""

from app.shared.auth.jwt import (
    KeycloakClaims,
    TokenClaims,
    decode_keycloak_token,
    decode_token,
    encode_token,
    generate_api_key,
    get_jwk_client,
    hash_api_key,
)
from app.shared.auth.permissions import (
    FGA_FUND_PERMISSIONS,
    FGA_PERMISSION_MAP,
    PERMISSION_TO_FGA,
    PLATFORM_ROLE_PERMISSIONS,
    ROLE_PERMISSIONS,
    Permission,
    PlatformRole,
    Role,
    get_actor_context,
    require_permission,
    require_platform_permission,
    resolve_permissions,
)
from app.shared.auth.request_context import (
    DEFAULT_FUND_SLUG,
    SYSTEM_CONTEXT,
    ActorType,
    RequestContext,
    get_request_context,
    get_request_context_or_system,
    set_request_context,
)
from app.shared.auth.token_revocation import TokenRevocationService

__all__ = [
    # request_context
    "ActorType",
    "DEFAULT_FUND_SLUG",
    "RequestContext",
    "SYSTEM_CONTEXT",
    "get_request_context",
    "get_request_context_or_system",
    "set_request_context",
    # jwt
    "KeycloakClaims",
    "TokenClaims",
    "decode_keycloak_token",
    "decode_token",
    "encode_token",
    "generate_api_key",
    "get_jwk_client",
    "hash_api_key",
    # token_revocation
    "TokenRevocationService",
    # permissions
    "FGA_FUND_PERMISSIONS",
    "FGA_PERMISSION_MAP",
    "PERMISSION_TO_FGA",
    "PLATFORM_ROLE_PERMISSIONS",
    "Permission",
    "PlatformRole",
    "ROLE_PERMISSIONS",
    "Role",
    "get_actor_context",
    "require_permission",
    "require_platform_permission",
    "resolve_permissions",
]

# Startup check: ensure SYSTEM_CONTEXT permissions stay in sync with ADMIN role.
# These are defined in separate files to avoid circular imports, so this
# cross-module assertion catches drift when a developer adds a new permission.
_admin_perm_values = frozenset(p.value for p in ROLE_PERMISSIONS[Role.ADMIN])
_system_perm_values = SYSTEM_CONTEXT.permissions
_missing = _admin_perm_values - _system_perm_values
_extra = _system_perm_values - _admin_perm_values
if _missing or _extra:
    raise RuntimeError(
        f"SYSTEM_CONTEXT permissions out of sync with ROLE_PERMISSIONS[ADMIN]. "
        f"Missing: {sorted(_missing)}. Extra: {sorted(_extra)}. "
        f"Update _ALL_PERMISSIONS in request_context.py."
    )
