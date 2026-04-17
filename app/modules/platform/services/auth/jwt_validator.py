"""JWT parsing, signature validation, and token exchange.

Handles both app-issued HS256 tokens and Keycloak-issued RS256 tokens.
Does NOT touch repositories, FGA, or DB — pure token cryptography + claims
parsing.  Composed into ``AuthService`` via constructor injection.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import jwt as pyjwt
import structlog
from jwt import PyJWTError

from app.shared.auth import (
    TokenClaims,
    decode_token,
    encode_token,
    resolve_permissions,
)
from app.shared.auth.jwt import resolve_customer_realm
from app.shared.auth.request_context import ActorType, RequestContext
from app.shared.errors import AuthenticationError

logger = structlog.get_logger()


@dataclass(frozen=True)
class RS256TokenPeek:
    """Result of peeking (without verification) at an RS256 token's issuer."""

    issuer: str
    claims: dict[str, Any]


class JWTValidator:
    """Encapsulates JWT cryptography: HS256 and Keycloak RS256 token handling.

    This class is deliberately stateless w.r.t. external services — it does
    not talk to databases or FGA.  It holds only configuration (secrets,
    Keycloak endpoints, realm metadata) and dispatches to ``app.shared.auth``
    primitives.
    """

    def __init__(
        self,
        *,
        jwt_secret: str,
        jwt_algorithm: str = "HS256",
        jwt_expiry_minutes: int = 60,
        keycloak_url: str = "",
        keycloak_browser_url: str = "",
        keycloak_realm: str = "",
        keycloak_client_id: str = "",
        keycloak_ops_realm: str = "",
        keycloak_ops_client_id: str = "",
        keycloak_investors_realm: str = "",
        keycloak_investors_client_id: str = "",
    ) -> None:
        self._jwt_secret = jwt_secret
        self._jwt_algorithm = jwt_algorithm
        self._jwt_expiry_minutes = jwt_expiry_minutes
        self.keycloak_url = keycloak_url
        self.keycloak_browser_url = keycloak_browser_url
        self.keycloak_realm = keycloak_realm
        self.keycloak_client_id = keycloak_client_id
        self.keycloak_ops_realm = keycloak_ops_realm
        self.keycloak_ops_client_id = keycloak_ops_client_id
        self.keycloak_investors_realm = keycloak_investors_realm
        self.keycloak_investors_client_id = keycloak_investors_client_id

    # ----- HS256 (app-issued) tokens -----

    def create_token(
        self,
        *,
        actor_id: str,
        actor_type: ActorType,
        fund_slug: str | None = None,
        fund_id: str | None = None,
        customer_id: str | None = None,
        roles: list[str],
        delegated_by: str | None = None,
    ) -> str:
        """Issue a signed HS256 JWT."""
        return encode_token(
            actor_id=actor_id,
            actor_type=actor_type,
            fund_slug=fund_slug,
            fund_id=fund_id,
            customer_id=customer_id,
            roles=roles,
            secret=self._jwt_secret,
            algorithm=self._jwt_algorithm,
            expiry_minutes=self._jwt_expiry_minutes,
            delegated_by=delegated_by,
        )

    def decode_app_token(self, token: str) -> TokenClaims:
        """Validate an app-issued HS256 token and return its claims."""
        try:
            return decode_token(
                token, secret=self._jwt_secret, algorithm=self._jwt_algorithm
            )
        except PyJWTError as exc:
            logger.warning("jwt_validation_failed", error=str(exc))
            raise AuthenticationError("Invalid token", code="INVALID_TOKEN") from exc

    @staticmethod
    def claims_to_context(claims: TokenClaims) -> RequestContext:
        """Translate HS256 claims into a RequestContext."""
        roles = frozenset(claims.roles)
        return RequestContext(
            actor_id=claims.sub,
            actor_type=claims.actor_type,
            customer_id=claims.customer_id,
            home_customer_id=claims.customer_id,
            fund_slug=claims.fund_slug,
            fund_id=claims.fund_id,
            roles=roles,
            permissions=resolve_permissions(roles),
            delegated_by=claims.delegated_by,
        )

    # ----- Common helpers -----

    @staticmethod
    def token_hash(token: str) -> str:
        """Fast hash of the JWT signature (last segment) for cache keying.

        The signature is the unique part — hashing the full token is wasteful.
        """
        return hashlib.sha256(token.rpartition(".")[2].encode()).hexdigest()[:16]

    @staticmethod
    def unverified_header(token: str) -> dict[str, Any]:
        """Decode the JWT header without signature verification."""
        try:
            return pyjwt.get_unverified_header(token)
        except PyJWTError as exc:
            logger.warning("jwt_header_decode_failed")
            raise AuthenticationError(
                "Invalid token", code="INVALID_TOKEN"
            ) from exc

    @staticmethod
    def peek_rs256(token: str) -> RS256TokenPeek:
        """Decode an RS256 token's claims without signature verification.

        Used to inspect the ``iss`` claim and decide which Keycloak realm to
        validate against.  The caller is responsible for performing full
        signature verification afterwards.
        """
        try:
            claims = pyjwt.decode(token, options={"verify_signature": False})
        except PyJWTError as exc:
            logger.warning("jwt_unverified_decode_failed")
            raise AuthenticationError(
                "Invalid token", code="INVALID_TOKEN"
            ) from exc
        return RS256TokenPeek(issuer=claims.get("iss", ""), claims=claims)

    # ----- Realm resolution -----

    def resolve_fund_realm(
        self, acting_as_customer_id: str | None
    ) -> tuple[str, str]:
        """Resolve (realm, client_id) for a fund user request.

        If ``acting_as_customer_id`` is provided, look up that customer's
        dedicated realm; otherwise fall back to the default fund realm.
        """
        return resolve_customer_realm(
            acting_as_customer_id,
            default_realm=self.keycloak_realm,
            default_client_id=self.keycloak_client_id,
        )
