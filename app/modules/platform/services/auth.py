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

from app.modules.platform.interfaces.fund import FundInfo
from app.modules.platform.models.fund import FundStatus
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
from app.shared.auth.jwt import resolve_customer_realm
from app.shared.auth.request_context import ActorType, RequestContext
from app.shared.errors import AuthenticationError, AuthorizationError

if TYPE_CHECKING:
    from app.modules.platform.models.customer import CustomerRecord
    from app.modules.platform.models.fund import FundRecord
    from app.modules.platform.models.user import UserRecord
    from app.modules.platform.repositories import (
        APIKeyRepository,
        CustomerRepository,
        FundRepository,
        OperatorRepository,
        ServicingEdgeRepository,
        UserRepository,
    )
    from app.modules.capital_accounts.repositories.investor import InvestorRepository
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
        customer_repo: CustomerRepository | None = None,
        servicing_edge_repo: ServicingEdgeRepository | None = None,
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
        keycloak_investors_realm: str = "",
        keycloak_investors_client_id: str = "",
        investor_repo: InvestorRepository | None = None,
    ) -> None:
        self._user_repo = user_repo
        self._fund_repo = fund_repo
        self._operator_repo = operator_repo
        self._api_key_repo = api_key_repo
        self._customer_repo = customer_repo
        self._servicing_edge_repo = servicing_edge_repo
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
        self._keycloak_investors_realm = keycloak_investors_realm
        self._keycloak_investors_client_id = keycloak_investors_client_id
        self._investor_repo = investor_repo
        self._fga_cache: TTLCache[tuple[str, str], tuple[list[str], frozenset[str]]] = TTLCache(
            maxsize=_FGA_CACHE_MAX, ttl=_FGA_CACHE_TTL
        )
        # keycloak_sub → UserRecord (avoid upsert DB queries on every request)
        self._user_cache: TTLCache[str, UserRecord] = TTLCache(
            maxsize=_USER_CACHE_MAX, ttl=_USER_CACHE_TTL
        )
        # fund_slug → FundRecord (avoid fund lookup DB query on every request)
        self._fund_cache: TTLCache[str, FundRecord] = TTLCache(
            maxsize=_FUND_CACHE_MAX, ttl=_FUND_CACHE_TTL
        )
        # customer_id → CustomerRecord
        self._customer_cache: TTLCache[str, CustomerRecord] = TTLCache(
            maxsize=64, ttl=120
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

    async def authenticate_jwt(
        self,
        token: str,
        *,
        fund_slug: str | None = None,
        acting_as_customer_id: str | None = None,
    ) -> RequestContext:
        """Validate a JWT and return a RequestContext, or None if invalid.

        Detects Keycloak-issued tokens (RS256 with ``iss`` claim) vs
        app-issued tokens (HS256) and routes accordingly.
        """
        # Fast path: return cached context for repeated requests with same token
        ctx_key = (self._token_hash(token), fund_slug, acting_as_customer_id)
        cached_ctx: RequestContext | None = self._ctx_cache.get(ctx_key)
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
            elif self._keycloak_investors_realm and f"/realms/{self._keycloak_investors_realm}" in issuer:
                request_context = await self._authenticate_keycloak_investor(
                    token, fund_slug=fund_slug,
                )
            else:
                request_context = await self._authenticate_keycloak(
                    token, fund_slug=fund_slug, acting_as_customer_id=acting_as_customer_id
                )
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
        fund_customer_id: str | None = getattr(fund, "customer_id", None)
        return RequestContext(
            actor_id=record.id,
            actor_type=ActorType(record.actor_type),
            customer_id=fund_customer_id,
            home_customer_id=fund_customer_id,
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
        customer_id: str | None = None,
        roles: list[str],
        delegated_by: str | None = None,
    ) -> str:
        """Issue a signed JWT."""
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

    # ----- Keycloak fund user authentication -----

    async def _authenticate_keycloak(
        self,
        token: str,
        *,
        fund_slug: str | None,
        acting_as_customer_id: str | None = None,
    ) -> RequestContext:
        """Validate a Keycloak RS256 JWT for a fund user, resolve roles from FGA."""
        if not self._keycloak_url:
            logger.warning("keycloak_not_configured")
            raise AuthenticationError("Identity provider not configured", code="IDP_UNAVAILABLE")

        # Resolve realm: if acting_as_customer_id is provided, use that customer's
        # realm; otherwise fall back to the default fund realm.
        realm, client_id = resolve_customer_realm(
            acting_as_customer_id,
            default_realm=self._keycloak_realm,
            default_client_id=self._keycloak_client_id,
        )

        try:
            kc_claims = await decode_keycloak_token(
                token,
                keycloak_url=self._keycloak_url,
                realm=realm,
                client_id=client_id,
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
            from app.shared.fga.client import unqualify_object_id

            fga_fund_ids = await self._fga_client.list_objects(
                user=f"user:{user.id}", relation="can_read", type="fund"
            )
            if not fga_fund_ids:
                logger.warning("keycloak_user_no_fund_access", user_id=user.id)
                raise AuthorizationError("No fund access", code="NO_FUND_ACCESS")
            # Strip customer qualifier — FGA IDs are "{customer}/{fund}"
            fund_ids = sorted(unqualify_object_id(fid) for fid in fga_fund_ids)
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
        # customer_id is resolved below; use fund's customer_id for the FGA lookup
        roles, permissions = await self._resolve_fund_access(
            user.id, fund_id, getattr(fund, "customer_id", None),
        )
        if not roles and not permissions:
            logger.warning("keycloak_user_no_fund_role", user_id=user.id, fund_slug=fund_slug)
            raise AuthorizationError("No fund access", code="NO_FUND_ACCESS")

        # Resolve customer context from user and fund
        home_customer_id: str | None = getattr(user, "customer_id", None)
        fund_customer_id: str | None = getattr(fund, "customer_id", None)
        # X-Acting-As header overrides the target customer for delegated sessions
        target_customer_id = acting_as_customer_id or fund_customer_id
        customer_id = target_customer_id  # the active customer is always the target
        resolved_acting_as: str | None = None

        if (
            home_customer_id
            and target_customer_id
            and home_customer_id != target_customer_id
            and self._servicing_edge_repo is not None
        ):
            # Fund-admin user acting on a client customer's fund — delegated access.
            # Verify a servicing edge exists.
            edge = await self._servicing_edge_repo.get_active_edge(
                admin_customer_id=home_customer_id,
                client_customer_id=target_customer_id,
            )
            if edge is None:
                logger.warning(
                    "no_servicing_edge",
                    home_customer=home_customer_id,
                    target_customer=target_customer_id,
                )
                raise AuthorizationError(
                    "No servicing relationship", code="NO_SERVICING_EDGE"
                )
            # Intersect: user's roles limited to what the edge permits
            edge_roles = frozenset(edge.scoped_roles)
            roles = [r for r in roles if r in edge_roles]
            permissions = resolve_permissions(frozenset(roles))
            resolved_acting_as = target_customer_id

        return RequestContext(
            actor_id=user.id,
            actor_type=ActorType.USER,
            customer_id=customer_id,
            home_customer_id=home_customer_id,
            acting_as_customer_id=resolved_acting_as,
            fund_slug=fund_slug,
            fund_id=fund_id,
            roles=frozenset(roles),
            permissions=permissions,
        )

    async def _resolve_fund_access(
        self, user_id: str, fund_id: str, fund_customer_id: str | None = None
    ) -> tuple[list[str], frozenset[str]]:
        """Resolve fund user roles and permissions from FGA, with TTL cache.

        Queries FGA for both role relations (admin, analyst, ...) and
        permission relations (can_read_instruments, can_execute_trades, ...).
        FGA computes the union: permissions granted by role + direct grants.
        """
        cache_key = (user_id, fund_id, fund_customer_id)
        cached: tuple[list[str], frozenset[str]] | None = self._fga_cache.get(cache_key)
        if cached is not None:
            return cached

        if self._fga_client is None:
            return [], frozenset()

        from app.shared.fga.client import qualify_object_id

        fga_object = qualify_object_id("fund", fund_id, fund_customer_id)
        # Single FGA call resolves both roles and effective permissions
        all_relations = await self._fga_client.list_relations(
            user=f"user:{user_id}",
            object=fga_object,
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

    # ----- Keycloak investor authentication -----

    async def _authenticate_keycloak_investor(
        self,
        token: str,
        *,
        fund_slug: str | None,
    ) -> RequestContext:
        """Validate a Keycloak RS256 JWT from the investors realm."""
        if not self._keycloak_url:
            raise AuthenticationError("Identity provider not configured", code="IDP_UNAVAILABLE")
        if self._investor_repo is None:
            raise AuthenticationError("Investor auth not configured", code="IDP_UNAVAILABLE")

        try:
            kc_claims = await decode_keycloak_token(
                token,
                keycloak_url=self._keycloak_url,
                realm=self._keycloak_investors_realm,
                client_id=self._keycloak_investors_client_id,
                keycloak_browser_url=self._keycloak_browser_url,
            )
        except PyJWTError as e:
            logger.warning("investor_jwt_validation_failed", error=str(e))
            raise AuthenticationError("Invalid token", code="INVALID_TOKEN") from e

        # Look up investor by keycloak_sub (JIT sync).  If not yet linked,
        # fall back to email match and persist the keycloak_sub for next time.
        investor = await self._investor_repo.get_by_keycloak_sub(kc_claims.sub)
        if investor is None and kc_claims.email:
            investor = await self._investor_repo.get_by_email(kc_claims.email)
            if investor is not None:
                await self._investor_repo.update(
                    investor.id, keycloak_sub=kc_claims.sub
                )
        if investor is None:
            logger.warning("investor_keycloak_sub_not_found", sub=kc_claims.sub, email=kc_claims.email)
            raise AuthorizationError("Investor account not found", code="INVESTOR_NOT_FOUND")
        if not investor.is_active:
            raise AuthorizationError("Investor account is inactive", code="USER_INACTIVE")

        # Resolve fund — investor must specify which fund they want to view,
        # or we pick the first fund they have a capital account in.
        investor_fund_slug = fund_slug
        investor_fund_id: str | None = None
        fund_customer_id: str | None = None
        if investor_fund_slug:
            fund = await self._fund_repo.get_by_slug(investor_fund_slug)
            if fund is None or fund.status != FundStatus.ACTIVE:
                raise AuthorizationError("Fund not found", code="FUND_NOT_FOUND")
            investor_fund_id = fund.id
            fund_customer_id = getattr(fund, "customer_id", None)

            # Verify investor has FGA access to this fund
            if self._fga_client is not None:
                has_access = await self._fga_client.check(
                    user=f"investor:{investor.id}",
                    relation="can_read",
                    object=f"fund:{investor_fund_id}",
                )
                if not has_access:
                    raise AuthorizationError("Fund not found", code="FUND_NOT_FOUND")
        else:
            # Discover funds from FGA
            if self._fga_client is not None:
                from app.shared.fga.client import unqualify_object_id

                fga_fund_ids = await self._fga_client.list_objects(
                    user=f"investor:{investor.id}", relation="can_read", type="fund"
                )
                if fga_fund_ids:
                    fund_ids = sorted(unqualify_object_id(fid) for fid in fga_fund_ids)
                    fund = await self._fund_repo.get_by_id(fund_ids[0])
                    if fund is not None and fund.status == FundStatus.ACTIVE:
                        investor_fund_slug = fund.slug
                        investor_fund_id = fund.id
                        fund_customer_id = getattr(fund, "customer_id", None)

        roles = frozenset({Role.INVESTOR})
        permissions = resolve_permissions(roles)

        return RequestContext(
            actor_id=investor.id,
            actor_type=ActorType.INVESTOR,
            customer_id=fund_customer_id,
            home_customer_id=fund_customer_id,
            fund_slug=investor_fund_slug,
            fund_id=investor_fund_id,
            roles=roles,
            permissions=permissions,
        )

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
        # Cache keys are 3-tuples (user_id, fund_id, fund_customer_id) — evict
        # all entries matching the user+fund pair regardless of customer_id.
        keys_to_evict = [
            k for k in self._fga_cache if k[0] == user_id and k[1] == fund_id
        ]
        for k in keys_to_evict:
            self._fga_cache.pop(k, None)
        # Also clear context cache — roles/permissions may have changed.
        self._ctx_cache.clear()

    # ----- Public API -----

    async def get_user_funds(
        self, user_id: str, *, actor_type: ActorType = ActorType.USER
    ) -> list[FundInfo]:
        """Return funds the user/investor has access to (for /me/funds endpoint)."""
        if self._fga_client is None:
            return []

        from app.shared.fga.client import unqualify_object_id

        fga_type = "investor" if actor_type == ActorType.INVESTOR else "user"
        fga_fund_ids = await self._fga_client.list_objects(
            user=f"{fga_type}:{user_id}", relation="can_read", type="fund"
        )

        result: list[FundInfo] = []
        for fga_id in sorted(fga_fund_ids):
            fund_id = unqualify_object_id(fga_id)
            fund = await self._fund_repo.get_by_id(fund_id)
            if fund is None or fund.status != FundStatus.ACTIVE:
                continue
            if actor_type == ActorType.INVESTOR:
                role = "investor"
            else:
                roles, _perms = await self._resolve_fund_access(user_id, fund_id, fund.customer_id)
                role = roles[0] if roles else "viewer"
            # Resolve customer name if customer_repo is available
            customer_name: str | None = None
            if self._customer_repo is not None and fund.customer_id:
                customer = await self._customer_repo.get_by_id(fund.customer_id)
                customer_name = customer.name if customer else None
            result.append(
                FundInfo(
                    fund_slug=fund.slug,
                    fund_name=fund.name,
                    role=role,
                    customer_id=fund.customer_id,
                    customer_name=customer_name,
                )
            )

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

        roles, _perms = await self._resolve_fund_access(user.id, fund.id, fund.customer_id)
        if not roles:
            raise ValueError(f"User has no access to fund {fund_slug}")

        token = self.create_token(
            actor_id=user.id,
            actor_type=ActorType.USER,
            fund_slug=fund_slug,
            fund_id=fund.id,
            customer_id=fund.customer_id,
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
            customer_id=claims.customer_id,
            home_customer_id=claims.customer_id,
            fund_slug=claims.fund_slug,
            fund_id=claims.fund_id,
            roles=roles,
            permissions=resolve_permissions(roles),
            delegated_by=claims.delegated_by,
        )
