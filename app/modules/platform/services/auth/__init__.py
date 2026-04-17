"""Authentication service package.

Historically ``app.modules.platform.services.auth`` was a single module.
It has been split into three focused files while preserving the exact
public import surface:

- :mod:`jwt_validator` — JWT parsing, signature validation, token exchange
- :mod:`fga_client` — OpenFGA permission resolution, caching, revocation
- :mod:`orchestrator` — ``AuthService`` composing the two above

External callers continue to import from this package, e.g.::

    from app.modules.platform.services.auth import AuthService

The ``decode_keycloak_token`` symbol is re-exported here so that tests
using ``patch("app.modules.platform.services.auth.decode_keycloak_token")``
continue to work — the orchestrator resolves the symbol dynamically
through this module's namespace at call time.
"""

from __future__ import annotations

# Keep the legacy module-level imports so test patches on
# ``app.modules.platform.services.auth.<symbol>`` keep working.
from app.shared.auth import (
    FGA_FUND_PERMISSIONS,
    FGA_PERMISSION_MAP,
    PLATFORM_ROLE_PERMISSIONS,
    PlatformRole,
    Role,
    TokenClaims,
    decode_keycloak_token,
    decode_token,
    encode_token,
    hash_api_key,
    resolve_permissions,
)

from app.modules.platform.services.auth.fga_client import FGAResolver
from app.modules.platform.services.auth.jwt_validator import JWTValidator
from app.modules.platform.services.auth.orchestrator import AuthService

__all__ = [
    "AuthService",
    "FGAResolver",
    "JWTValidator",
    # Re-exports from app.shared.auth kept for patch targets + back-compat
    "FGA_FUND_PERMISSIONS",
    "FGA_PERMISSION_MAP",
    "PLATFORM_ROLE_PERMISSIONS",
    "PlatformRole",
    "Role",
    "TokenClaims",
    "decode_keycloak_token",
    "decode_token",
    "encode_token",
    "hash_api_key",
    "resolve_permissions",
]
