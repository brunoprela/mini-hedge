"""Authentication service — validates JWTs and API keys.

Produces a RequestContext for every authenticated request. The service lives
in the platform module because it owns users, API keys, and fund access.

Keycloak-issued JWTs (RS256) are validated via JWKS. App-issued JWTs (HS256)
are validated with the shared secret. Authorization is resolved entirely
from OpenFGA — there is no fund_memberships table.

Two Keycloak realms are supported:
- Fund realm (minihedge): fund personnel (users)
- Ops realm (minihedge-ops): platform operators
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import jwt as pyjwt
import structlog
from cachetools import TTLCache
from jwt import PyJWTError

from app.modules.platform.interface import FundInfo
from app.modules.platform.models import FundStatus
from app.shared.auth import (
    FGA_FUND_PERMISSIONS,
    FGA_PERMISSION_MAP,
    PLATFORM_ROLE_PERMISSIONS,
    PlatformRole,
    TokenClaims,
    decode_keycloak_token,
    decode_token,
    encode_token,
    hash_api_key,
    resolve_permissions,
)
from app.shared.errors import AuthenticationError, AuthorizationError
from app.shared.request_context import ActorType, RequestContext

if TYPE_CHECKING:
    from app.modules.platform.api_key_repository import APIKeyRepository
    from app.modules.platform.fund_repository import FundRepository
    from app.modules.platform.operator_repository import OperatorRepository
    from app.modules.platform.user_repository import UserRepository
    from app.shared.fga import FGAClient

logger = structlog.get_logger()

# FGA relation names for fund user roles
_FUND_USER_ROLES = [
    "admin",
    "portfolio_manager",
    "analyst",
    "risk_manager",
    "compliance_officer",
    "viewer",
]
_PLATFORM_ROLES = ["ops_admin", "ops_viewer"]

# Cache key: (actor_id, fund_id) → (roles, permissions)
_FGA_CACHE_MAX = 256
_FGA_CACHE_TTL = 30  # seconds

# User/fund caches — avoid DB round-trips on every request
_USER_CACHE_MAX = 256
_USER_CACHE_TTL = 60  # seconds — user data changes rarely
_FUND_CACHE_MAX = 64
_FUND_CACHE_TTL = 120  # seconds — fund metadata is near-static

# Full RequestContext cache keyed by (token_hash, fund_slug) — avoids ALL
# downstream calls (JWKS, FGA, DB) for repeated requests with the same JWT.
# The token only changes on refresh (every few minutes).
_CTX_CACHE_MAX = 256
_CTX_CACHE_TTL = 300  # seconds — JWT only changes on refresh (~5 min)


class AuthService:
    """Authenticates requests via JWT or API key."""

    def __init__(
        self,
        *,
        user_repo: UserRepository,
        fund_repo: FundRepository,
        operator_repo: OperatorRepository,
        api_key_repo: APIKeyRepository,
        fga_client: FGAClient | None = None,
        jwt_secret: str,
        jwt_algorithm: str = "HS256",
        jwt_expiry_minutes: int = 60,
        keycloak_url: str = "",
        keycloak_browser_url: str = "",
        keycloak_realm: str = "",
        keycloak_client_id: str = "",
        keycloak_ops_realm: str = "",
        keycloak_ops_client_id: str = "",
    ) -> None:
        self._user_repo = user_repo
        self._fund_repo = fund_repo
        self._operator_repo = operator_repo
        self._api_key_repo = api_key_repo
        self._fga_client = fga_client
        self._jwt_secret = jwt_secret
        self._jwt_algorithm = jwt_algorithm
        self._jwt_expiry_minutes = jwt_expiry_minutes
        self._keycloak_url = keycloak_url
        self._keycloak_browser_url = keycloak_browser_url
        self._keycloak_realm = keycloak_realm
        self._keycloak_client_id = keycloak_client_id
        self._keycloak_ops_realm = keycloak_ops_realm
        self._keycloak_ops_client_id = keycloak_ops_client_id
        self._fga_cache: TTLCache[tuple[str, str], tuple[list[str], frozenset[str]]] = TTLCache(
            maxsize=_FGA_CACHE_MAX, ttl=_FGA_CACHE_TTL
        )
        # keycloak_sub → UserRecord (avoid upsert DB queries on every request)
        self._user_cache: TTLCache[str, object] = TTLCache(
            maxsize=_USER_CACHE_MAX, ttl=_USER_CACHE_TTL
        )
        # fund_slug → FundRecord (avoid fund lookup DB query on every request)
        self._fund_cache: TTLCache[str, object] = TTLCache(
            maxsize=_FUND_CACHE_MAX, ttl=_FUND_CACHE_TTL
        )
        # (token_hash, fund_slug) → RequestContext — skip ALL downstream calls
        self._ctx_cache: TTLCache[tuple[str, str | None], RequestContext] = TTLCache(
            maxsize=_CTX_CACHE_MAX, ttl=_CTX_CACHE_TTL
        )

    @staticmethod
    def _token_hash(token: str) -> str:
        """Fast hash of the JWT signature (last segment) for cache keying."""
        # The signature is the unique part — no need to hash the full token.
        return hashlib.sha256(token.rpartition(".")[2].encode()).hexdigest()[:16]

    async def authenticate_jwt(self, token: str, *, fund_slug: str | None = None) -> RequestContext:
        """Validate a JWT and return a RequestContext, or None if invalid.

        Detects Keycloak-issued tokens (RS256 with ``iss`` claim) vs
        app-issued tokens (HS256) and routes accordingly.
        """
        # Fast path: return cached context for repeated requests with same token
        ctx_key = (self._token_hash(token), fund_slug)
        cached_ctx = self._ctx_cache.get(ctx_key)
        if cached_ctx is not None:
            return cached_ctx

        try:
            header = pyjwt.get_unverified_header(token)
        except PyJWTError as exc:
            logger.warning("jwt_header_decode_failed")
            raise AuthenticationError("Invalid token", code="INVALID_TOKEN") from exc

        if header.get("alg") == "RS256":
            # Peek at unverified issuer to determine realm
            try:
                unverified = pyjwt.decode(token, options={"verify_signature": False})
            except PyJWTError as exc:
                logger.warning("jwt_unverified_decode_failed")
                raise AuthenticationError("Invalid token", code="INVALID_TOKEN") from exc

            issuer = unverified.get("iss", "")
            if self._keycloak_ops_realm and f"/realms/{self._keycloak_ops_realm}" in issuer:
                request_context = await self._authenticate_keycloak_operator(token)
            else:
                request_context = await self._authenticate_keycloak(token, fund_slug=fund_slug)
        else:
            # App-issued HS256 token (agent tokens, legacy)
            try:
                claims = decode_token(token, secret=self._jwt_secret, algorithm=self._jwt_algorithm)
            except PyJWTError as e:
                logger.warning("jwt_validation_failed", error=str(e))
                raise AuthenticationError("Invalid token", code="INVALID_TOKEN") from e
            request_context = self._claims_to_context(claims)

        self._ctx_cache[ctx_key] = request_context
        return request_context

    async def authenticate_api_key(self, raw_key: str) -> RequestContext:
        """Validate an API key and return a RequestContext, or None if invalid."""
        key_hash = hash_api_key(raw_key)
        record = await self._api_key_repo.get_by_hash(key_hash)
        if record is None:
            logger.warning("api_key_not_found")
            raise AuthenticationError("Invalid API key", code="INVALID_TOKEN")

        fund = await self._fund_repo.get_by_id(record.fund_id)
        if fund is None or fund.status != FundStatus.ACTIVE:
            logger.warning("api_key_fund_inactive", fund_id=record.fund_id)
            raise AuthorizationError("Fund inactive or not found", code="FUND_INACTIVE")

        roles = frozenset(record.roles)
        return RequestContext(
            actor_id=record.id,
            actor_type=ActorType(record.actor_type),
            fund_slug=fund.slug,
            fund_id=fund.id,
            roles=roles,
            permissions=resolve_permissions(roles),
        )

    def create_token(
        self,
        *,
        actor_id: str,
        actor_type: ActorType,
        fund_slug: str | None = None,
        fund_id: str | None = None,
        roles: list[str],
        delegated_by: str | None = None,
    ) -> str:
        """Issue a signed JWT."""
        return encode_token(
            actor_id=actor_id,
            actor_type=actor_type,
            fund_slug=fund_slug,
            fund_id=fund_id,
            roles=roles,
            secret=self._jwt_secret,
            algorithm=self._jwt_algorithm,
            expiry_minutes=self._jwt_expiry_minutes,
            delegated_by=delegated_by,
        )

    # ----- Keycloak fund user authentication -----

    async def _authenticate_keycloak(self, token: str, *, fund_slug: str | None) -> RequestContext:
        """Validate a Keycloak RS256 JWT for a fund user, resolve roles from FGA."""
        if not self._keycloak_url:
            logger.warning("keycloak_not_configured")
            raise AuthenticationError("Identity provider not configured", code="IDP_UNAVAILABLE")

        try:
            kc_claims = await decode_keycloak_token(
                token,
                keycloak_url=self._keycloak_url,
                realm=self._keycloak_realm,
                client_id=self._keycloak_client_id,
                keycloak_browser_url=self._keycloak_browser_url,
            )
        except PyJWTError as e:
            logger.warning("keycloak_jwt_validation_failed", error=str(e))
            raise AuthenticationError("Invalid token", code="INVALID_TOKEN") from e

        # JIT user sync — cached to avoid DB round-trips on every request
        cached_user = self._user_cache.get(kc_claims.sub)
        if cached_user is not None:
            user = cached_user
        else:
            user = await self._user_repo.upsert_from_keycloak(
                keycloak_sub=kc_claims.sub,
                email=kc_claims.email,
                name=kc_claims.name,
            )
            self._user_cache[kc_claims.sub] = user
        if not user.is_active:
            logger.warning("keycloak_user_inactive", user_id=user.id)
            raise AuthorizationError("User account is inactive", code="USER_INACTIVE")

        # Resolve fund + roles from FGA
        if fund_slug is None:
            # No fund specified — discover from FGA
            if self._fga_client is None:
                logger.warning("fga_not_available_for_fund_discovery")
                raise AuthenticationError(
                    "Authorization service unavailable",
                    code="FGA_UNAVAILABLE",
                )
            fund_ids = await self._fga_client.list_objects(
                user=f"user:{user.id}", relation="can_read", type="fund"
            )
            if not fund_ids:
                logger.warning("keycloak_user_no_fund_access", user_id=user.id)
                raise AuthorizationError("No fund access", code="NO_FUND_ACCESS")
            # Pick first fund (deterministic via sorted IDs)
            fund_ids.sort()
            fund = await self._fund_repo.get_by_id(fund_ids[0])
            if fund is None or fund.status != FundStatus.ACTIVE:
                logger.warning("keycloak_fund_inactive", fund_id=fund_ids[0])
                raise AuthorizationError("Fund inactive", code="FUND_INACTIVE")
            fund_slug = fund.slug
            fund_id = fund.id
        else:
            cached_fund = self._fund_cache.get(fund_slug)
            if cached_fund is not None:
                fund = cached_fund
            else:
                fund = await self._fund_repo.get_by_slug(fund_slug)
                if fund is not None:
                    self._fund_cache[fund_slug] = fund
            if fund is None:
                logger.warning("keycloak_fund_not_found", fund_slug=fund_slug)
                raise AuthorizationError("Fund not found", code="FUND_NOT_FOUND")
            if fund.status != FundStatus.ACTIVE:
                logger.warning("keycloak_fund_inactive", fund_slug=fund_slug)
                raise AuthorizationError("Fund inactive", code="FUND_INACTIVE")
            fund_id = fund.id

        # Resolve roles + permissions from FGA (with cache)
        roles, permissions = await self._resolve_fund_access(user.id, fund_id)
        if not roles and not permissions:
            logger.warning("keycloak_user_no_fund_role", user_id=user.id, fund_slug=fund_slug)
            raise AuthorizationError("No fund access", code="NO_FUND_ACCESS")

        return RequestContext(
            actor_id=user.id,
            actor_type=ActorType.USER,
            fund_slug=fund_slug,
            fund_id=fund_id,
            roles=frozenset(roles),
            permissions=permissions,
        )

    async def _resolve_fund_access(
        self, user_id: str, fund_id: str
    ) -> tuple[list[str], frozenset[str]]:
        """Resolve fund user roles and permissions from FGA, with TTL cache.

        Queries FGA for both role relations (admin, analyst, ...) and
        permission relations (can_read_instruments, can_execute_trades, ...).
        FGA computes the union: permissions granted by role + direct grants.
        """
        cache_key = (user_id, fund_id)
        cached = self._fga_cache.get(cache_key)
        if cached is not None:
            return cached

        if self._fga_client is None:
            return [], frozenset()

        # Single FGA call resolves both roles and effective permissions
        all_relations = await self._fga_client.list_relations(
            user=f"user:{user_id}",
            object=f"fund:{fund_id}",
            relations=_FUND_USER_ROLES + FGA_FUND_PERMISSIONS,
        )

        roles_set = set(_FUND_USER_ROLES)
        roles = [r for r in all_relations if r in roles_set]
        permissions = frozenset(
            FGA_PERMISSION_MAP[r] for r in all_relations if r in FGA_PERMISSION_MAP
        )

        result = (roles, permissions)
        self._fga_cache[cache_key] = result
        return result

    # ----- Keycloak operator authentication -----

    async def _authenticate_keycloak_operator(self, token: str) -> RequestContext:
        """Validate a Keycloak RS256 JWT from the ops realm, resolve platform role from FGA."""
        if not self._keycloak_url:
            logger.warning("keycloak_not_configured")
            raise AuthenticationError("Identity provider not configured", code="IDP_UNAVAILABLE")

        try:
            kc_claims = await decode_keycloak_token(
                token,
                keycloak_url=self._keycloak_url,
                realm=self._keycloak_ops_realm,
                client_id=self._keycloak_ops_client_id,
                keycloak_browser_url=self._keycloak_browser_url,
            )
        except PyJWTError as e:
            logger.warning("keycloak_ops_jwt_validation_failed", error=str(e))
            raise AuthenticationError("Invalid token", code="INVALID_TOKEN") from e

        # JIT operator sync
        operator = await self._operator_repo.upsert_from_keycloak(
            keycloak_sub=kc_claims.sub,
            email=kc_claims.email,
            name=kc_claims.name,
        )
        if not operator.is_active:
            logger.warning("keycloak_operator_inactive", operator_id=operator.id)
            raise AuthorizationError("Operator account is inactive", code="USER_INACTIVE")

        # Resolve platform role from FGA
        platform_roles: list[str] = []
        if self._fga_client is not None:
            platform_roles = await self._fga_client.list_relations(
                user=f"operator:{operator.id}",
                object="platform:global",
                relations=_PLATFORM_ROLES,
            )

        if not platform_roles:
            logger.warning("operator_no_platform_role", operator_id=operator.id)
            raise AuthorizationError("No platform role assigned", code="NO_PLATFORM_ROLE")

        # Use highest privilege role
        platform_role = "ops_admin" if "ops_admin" in platform_roles else platform_roles[0]

        # Resolve permissions from platform role
        try:
            pr = PlatformRole(platform_role)
            permissions = PLATFORM_ROLE_PERMISSIONS[pr]
        except (ValueError, KeyError):
            permissions = frozenset()

        return RequestContext(
            actor_id=operator.id,
            actor_type=ActorType.OPERATOR,
            platform_role=platform_role,
            roles=frozenset(platform_roles),
            permissions=frozenset(p.value for p in permissions),
        )

    # ----- Cache management -----

    def invalidate_fga_cache(self, user_id: str, fund_id: str) -> None:
        """Evict a cached FGA role lookup so access changes take effect immediately."""
        self._fga_cache.pop((user_id, fund_id), None)
        # Also clear context cache — roles/permissions may have changed.
        self._ctx_cache.clear()

    # ----- Public API -----

    async def get_user_funds(self, user_id: str) -> list[FundInfo]:
        """Return funds the user has access to (for /me/funds endpoint)."""
        if self._fga_client is None:
            return []

        fund_ids = await self._fga_client.list_objects(
            user=f"user:{user_id}", relation="can_read", type="fund"
        )

        result: list[FundInfo] = []
        for fund_id in sorted(fund_ids):
            fund = await self._fund_repo.get_by_id(fund_id)
            if fund is None or fund.status != FundStatus.ACTIVE:
                continue
            roles, _perms = await self._resolve_fund_access(user_id, fund_id)
            role = roles[0] if roles else "viewer"
            result.append(FundInfo(fund_slug=fund.slug, fund_name=fund.name, role=role))

        return result

    async def issue_user_token(self, email: str, fund_slug: str) -> tuple[str, str, list[str]]:
        """Validate a user + fund access and return (token, fund_slug, roles).

        Raises ValueError with a human-readable message on failure.
        """
        user = await self._user_repo.get_by_email(email)
        if user is None or not user.is_active:
            raise ValueError("Unknown or inactive user")

        fund = await self._fund_repo.get_by_slug(fund_slug)
        if fund is None:
            raise ValueError(f"Fund not found: {fund_slug}")

        roles, _perms = await self._resolve_fund_access(user.id, fund.id)
        if not roles:
            raise ValueError(f"User has no access to fund {fund_slug}")

        token = self.create_token(
            actor_id=user.id,
            actor_type=ActorType.USER,
            fund_slug=fund_slug,
            fund_id=fund.id,
            roles=roles,
        )
        return token, fund_slug, roles

    def issue_agent_token(
        self,
        *,
        agent_id: str,
        fund_slug: str,
        fund_id: str | None = None,
        roles: list[str],
        delegated_by: str,
    ) -> str:
        """Issue a JWT scoped to *fund_slug* for an LLM agent."""
        return self.create_token(
            actor_id=agent_id,
            actor_type=ActorType.AGENT,
            fund_slug=fund_slug,
            fund_id=fund_id,
            roles=roles,
            delegated_by=delegated_by,
        )

    def _claims_to_context(self, claims: TokenClaims) -> RequestContext:
        roles = frozenset(claims.roles)
        return RequestContext(
            actor_id=claims.sub,
            actor_type=claims.actor_type,
            fund_slug=claims.fund_slug,
            fund_id=claims.fund_id,
            roles=roles,
            permissions=resolve_permissions(roles),
            delegated_by=claims.delegated_by,
        )
