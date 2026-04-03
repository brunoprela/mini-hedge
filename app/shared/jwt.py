"""JWT encode/decode for app-issued and Keycloak tokens, plus API key hashing.

Separated from auth.py to keep the shared kernel focused. auth.py retains
RBAC definitions and FastAPI dependencies; this module handles token mechanics.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from jwt import PyJWKClient, PyJWTError
from pydantic import BaseModel, ConfigDict

from app.shared.request_context import ActorType

# ---------------------------------------------------------------------------
# App-issued JWT (HS256)
# ---------------------------------------------------------------------------


class TokenClaims(BaseModel):
    """Decoded JWT payload."""

    model_config = ConfigDict(frozen=True)

    sub: str  # actor ID
    actor_type: ActorType
    fund_slug: str | None = None
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
    fund_slug: str | None = None,
    fund_id: str | None = None,
    roles: list[str],
    secret: str,
    algorithm: str = "HS256",
    expiry_minutes: int = 60,
    delegated_by: str | None = None,
) -> str:
    """Create a signed JWT."""
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": actor_id,
        "actor_type": actor_type.value,
        "roles": roles,
        "iat": now,
        "exp": now + timedelta(minutes=expiry_minutes),
        "jti": str(uuid4()),
    }
    if fund_slug:
        payload["fund_slug"] = fund_slug
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
# Keycloak JWKS token validation (RS256)
# ---------------------------------------------------------------------------


class KeycloakClaims(BaseModel):
    """Decoded Keycloak JWT payload."""

    model_config = ConfigDict(frozen=True)

    sub: str  # Keycloak user ID (UUID)
    email: str
    name: str = ""
    email_verified: bool = False


_jwk_clients: dict[str, PyJWKClient] = {}


def get_jwk_client(keycloak_url: str, realm: str) -> PyJWKClient:
    """Get or create a cached PyJWKClient for the Keycloak realm."""
    jwks_url = f"{keycloak_url}/realms/{realm}/protocol/openid-connect/certs"
    if jwks_url not in _jwk_clients:
        _jwk_clients[jwks_url] = PyJWKClient(jwks_url, cache_keys=True)
    return _jwk_clients[jwks_url]


def decode_keycloak_token(
    token: str,
    *,
    keycloak_url: str,
    realm: str,
    client_id: str,
    keycloak_browser_url: str = "",
) -> KeycloakClaims:
    """Decode and validate a Keycloak-issued JWT using JWKS.

    Raises jwt.PyJWTError on failure (expired, bad signature, wrong audience).
    On key-not-found, refreshes the JWKS cache once and retries.
    """
    jwk_client = get_jwk_client(keycloak_url, realm)
    jwks_url = f"{keycloak_url}/realms/{realm}/protocol/openid-connect/certs"
    try:
        signing_key = jwk_client.get_signing_key_from_jwt(token)
    except PyJWTError:
        # Key mismatch — Keycloak may have rotated keys. Force cache refresh.
        _jwk_clients.pop(jwks_url, None)
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
