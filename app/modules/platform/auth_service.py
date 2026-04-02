"""Authentication service — validates JWTs and API keys against the database.

Produces a RequestContext for every authenticated request. The service lives
in the platform module because it owns users, API keys, and fund memberships.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from jwt import PyJWTError

from app.shared.auth import (
    TokenClaims,
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
    ) -> None:
        self._user_repo = user_repo
        self._fund_repo = fund_repo
        self._membership_repo = membership_repo
        self._api_key_repo = api_key_repo
        self._jwt_secret = jwt_secret
        self._jwt_algorithm = jwt_algorithm
        self._jwt_expiry_minutes = jwt_expiry_minutes

    async def authenticate_jwt(self, token: str) -> RequestContext | None:
        """Validate a JWT and return a RequestContext, or None if invalid."""
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
        if fund is None or fund.status != "active":
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
