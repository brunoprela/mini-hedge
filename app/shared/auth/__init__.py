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
