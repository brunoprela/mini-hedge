"""Authentication service — validates JWTs and API keys against the database.

Produces a RequestContext for every authenticated request. The service lives
in the platform module because it owns users, API keys, and fund memberships.

Keycloak-issued JWTs (RS256) are validated via JWKS. App-issued JWTs (HS256)
are validated with the shared secret. Fund membership lookups are cached with
a 30-second TTL to avoid hitting the database on every request.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import jwt as pyjwt
import structlog
from cachetools import TTLCache
from jwt import PyJWTError

from app.modules.platform.models import FundStatus
from app.shared.auth import (
    TokenClaims,
    decode_keycloak_token,
    decode_token,
    encode_token,
    hash_api_key,
    resolve_permissions,
)
from app.shared.request_context import ActorType, RequestContext

if TYPE_CHECKING:
    from app.modules.platform.repository import (
        APIKeyRepository,
        FundMembershipRepository,
        FundRepository,
        UserRepository,
    )

logger = structlog.get_logger()

# Cache key: (user_id, fund_slug) → (role, fund_slug)
_MEMBERSHIP_CACHE_MAX = 256
_MEMBERSHIP_CACHE_TTL = 30  # seconds


class AuthService:
    """Authenticates requests via JWT or API key."""

    def __init__(
        self,
        *,
        user_repo: UserRepository,
        fund_repo: FundRepository,
        membership_repo: FundMembershipRepository,
        api_key_repo: APIKeyRepository,
        jwt_secret: str,
        jwt_algorithm: str = "HS256",
        jwt_expiry_minutes: int = 60,
        keycloak_url: str = "",
        keycloak_browser_url: str = "",
        keycloak_realm: str = "",
        keycloak_client_id: str = "",
    ) -> None:
        self._user_repo = user_repo
        self._fund_repo = fund_repo
        self._membership_repo = membership_repo
        self._api_key_repo = api_key_repo
        self._jwt_secret = jwt_secret
        self._jwt_algorithm = jwt_algorithm
        self._jwt_expiry_minutes = jwt_expiry_minutes
        self._keycloak_url = keycloak_url
        self._keycloak_browser_url = keycloak_browser_url
        self._keycloak_realm = keycloak_realm
        self._keycloak_client_id = keycloak_client_id
        self._membership_cache: TTLCache[tuple[str, str], str] = TTLCache(
            maxsize=_MEMBERSHIP_CACHE_MAX, ttl=_MEMBERSHIP_CACHE_TTL
        )

    async def authenticate_jwt(
        self, token: str, *, fund_slug: str | None = None
    ) -> RequestContext | None:
        """Validate a JWT and return a RequestContext, or None if invalid.

        Detects Keycloak-issued tokens (RS256 with ``iss`` claim) vs
        app-issued tokens (HS256) and routes accordingly.
        """
        # Peek at the token header to determine the algorithm
        try:
            header = pyjwt.get_unverified_header(token)
        except PyJWTError:
            logger.warning("jwt_header_decode_failed")
            return None

        if header.get("alg") == "RS256":
            return await self._authenticate_keycloak(token, fund_slug=fund_slug)

        # App-issued HS256 token (agent tokens, legacy)
        try:
            claims = decode_token(token, secret=self._jwt_secret, algorithm=self._jwt_algorithm)
        except PyJWTError as e:
            logger.warning("jwt_validation_failed", error=str(e))
            return None

        return self._claims_to_context(claims)

    async def authenticate_api_key(self, raw_key: str) -> RequestContext | None:
        """Validate an API key and return a RequestContext, or None if invalid."""
        key_hash = hash_api_key(raw_key)
        record = await self._api_key_repo.get_by_hash(key_hash)
        if record is None:
            logger.warning("api_key_not_found")
            return None

        fund = await self._fund_repo.get_by_id(record.fund_id)
        if fund is None or fund.status != FundStatus.ACTIVE:
            logger.warning("api_key_fund_inactive", fund_id=record.fund_id)
            return None

        roles = frozenset(record.roles)
        return RequestContext(
            actor_id=record.id,
            actor_type=ActorType(record.actor_type),
            fund_slug=fund.slug,
            roles=roles,
            permissions=resolve_permissions(roles),
        )

    def create_token(
        self,
        *,
        actor_id: str,
        actor_type: ActorType,
        fund_slug: str,
        roles: list[str],
        delegated_by: str | None = None,
    ) -> str:
        """Issue a signed JWT."""
        return encode_token(
            actor_id=actor_id,
            actor_type=actor_type,
            fund_slug=fund_slug,
            roles=roles,
            secret=self._jwt_secret,
            algorithm=self._jwt_algorithm,
            expiry_minutes=self._jwt_expiry_minutes,
            delegated_by=delegated_by,
        )

    async def _authenticate_keycloak(
        self, token: str, *, fund_slug: str | None
    ) -> RequestContext | None:
        """Validate a Keycloak RS256 JWT, JIT-sync the user, resolve fund membership."""
        if not self._keycloak_url:
            logger.warning("keycloak_not_configured")
            return None

        try:
            kc_claims = decode_keycloak_token(
                token,
                keycloak_url=self._keycloak_url,
                realm=self._keycloak_realm,
                client_id=self._keycloak_client_id,
                keycloak_browser_url=self._keycloak_browser_url,
            )
        except PyJWTError as e:
            logger.warning("keycloak_jwt_validation_failed", error=str(e))
            return None

        # JIT user sync
        user = await self._user_repo.upsert_from_keycloak(
            keycloak_sub=kc_claims.sub,
            email=kc_claims.email,
            name=kc_claims.name,
        )
        if not user.is_active:
            logger.warning("keycloak_user_inactive", user_id=user.id)
            return None

        # Resolve fund membership (with cache)
        if fund_slug is None:
            # Default to first fund the user belongs to
            memberships = await self._membership_repo.get_by_user(user.id)
            if not memberships:
                logger.warning("keycloak_user_no_memberships", user_id=user.id)
                return None
            membership = memberships[0]
            fund = await self._fund_repo.get_by_id(membership.fund_id)
            if fund is None:
                return None
            fund_slug = fund.slug
            role = membership.role
        else:
            cache_key = (user.id, fund_slug)
            cached_role = self._membership_cache.get(cache_key)
            if cached_role is not None:
                role = cached_role
            else:
                fund = await self._fund_repo.get_by_slug(fund_slug)
                if fund is None:
                    logger.warning("keycloak_fund_not_found", fund_slug=fund_slug)
                    return None
                membership = await self._membership_repo.get_by_user_and_fund(user.id, fund.id)
                if membership is None:
                    logger.warning(
                        "keycloak_user_not_member",
                        user_id=user.id,
                        fund_slug=fund_slug,
                    )
                    return None
                role = membership.role
                self._membership_cache[cache_key] = role

        roles = frozenset({role})
        return RequestContext(
            actor_id=user.id,
            actor_type=ActorType.USER,
            fund_slug=fund_slug,
            roles=roles,
            permissions=resolve_permissions(roles),
        )

    async def get_user_funds(self, user_id: str) -> list[dict[str, str]]:
        """Return funds the user has access to (for /me/funds endpoint)."""
        pairs = await self._membership_repo.get_funds_for_user(user_id)
        return [
            {"fund_slug": fund.slug, "fund_name": fund.name, "role": membership.role}
            for fund, membership in pairs
        ]

    async def issue_user_token(self, email: str, fund_slug: str) -> tuple[str, str, list[str]]:
        """Validate a user + fund membership and return (token, fund_slug, roles).

        Raises ValueError with a human-readable message on failure.
        """
        user = await self._user_repo.get_by_email(email)
        if user is None or not user.is_active:
            raise ValueError("Unknown or inactive user")

        fund = await self._fund_repo.get_by_slug(fund_slug)
        if fund is None:
            raise ValueError(f"Fund not found: {fund_slug}")

        membership = await self._membership_repo.get_by_user_and_fund(user.id, fund.id)
        if membership is None:
            raise ValueError(f"User has no access to fund {fund_slug}")

        roles = [membership.role]
        token = self.create_token(
            actor_id=user.id,
            actor_type=ActorType.USER,
            fund_slug=fund_slug,
            roles=roles,
        )
        return token, fund_slug, roles

    def issue_agent_token(
        self,
        *,
        agent_id: str,
        fund_slug: str,
        roles: list[str],
        delegated_by: str,
    ) -> str:
        """Issue a JWT scoped to *fund_slug* for an LLM agent."""
        return self.create_token(
            actor_id=agent_id,
            actor_type=ActorType.AGENT,
            fund_slug=fund_slug,
            roles=roles,
            delegated_by=delegated_by,
        )

    def _claims_to_context(self, claims: TokenClaims) -> RequestContext:
        roles = frozenset(claims.roles)
        return RequestContext(
            actor_id=claims.sub,
            actor_type=claims.actor_type,
            fund_slug=claims.fund_slug,
            roles=roles,
            permissions=resolve_permissions(roles),
            delegated_by=claims.delegated_by,
        )
