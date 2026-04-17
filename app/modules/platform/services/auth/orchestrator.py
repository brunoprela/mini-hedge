"""AuthService — orchestrates JWT validation + FGA authorization.

Composes :class:`JWTValidator` (token cryptography) and :class:`FGAResolver`
(permission lookups) and adds the stateful glue: user / fund / customer
caches, JIT user sync, servicing-edge delegation, and request-context
caching.  Callers should import ``AuthService`` from
``app.modules.platform.services.auth`` (the package), which re-exports it.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from cachetools import TTLCache
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.modules.platform.interfaces.fund import FundInfo
from app.modules.platform.models.fund import FundStatus
from app.modules.platform.services.auth.fga_client import FGAResolver
from app.modules.platform.services.auth.jwt_validator import JWTValidator

# Re-exports — these names must live on the `auth` package module too,
# because tests patch ``app.modules.platform.services.auth.decode_keycloak_token``
# and similar symbols.  The orchestrator looks them up dynamically via
# ``sys.modules`` so patches take effect regardless of import timing.
from app.shared.auth import (
    PLATFORM_ROLE_PERMISSIONS,
    PlatformRole,
    Role,
    TokenClaims,
    decode_keycloak_token,
    hash_api_key,
    resolve_permissions,
)
from app.shared.auth.request_context import ActorType, RequestContext
from app.shared.circuit_breaker import CircuitBreaker, CircuitOpenError
from app.shared.errors import AuthenticationError, AuthorizationError

import structlog

if TYPE_CHECKING:
    from app.modules.platform.repositories.investor import InvestorRepository
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
    from app.shared.fga import FGAClient

logger = structlog.get_logger()

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

# Module path for dynamic lookup of patched symbols.  Tests patch
# ``app.modules.platform.services.auth.decode_keycloak_token``; resolving
# through ``sys.modules`` at call time ensures those patches are honoured.
_AUTH_PKG = "app.modules.platform.services.auth"


def _decode_keycloak_token_dynamic(*args, **kwargs):
    """Call ``decode_keycloak_token`` via the package namespace.

    Tests patch ``app.modules.platform.services.auth.decode_keycloak_token``
    and expect the orchestrator's calls to honour that patch.  Looking up
    the symbol on the package module at call time preserves that contract.
    """
    pkg = sys.modules.get(_AUTH_PKG)
    fn = getattr(pkg, "decode_keycloak_token", decode_keycloak_token) if pkg else decode_keycloak_token
    return fn(*args, **kwargs)


async def _decode_keycloak_token_with_retry(*args, **kwargs):
    """Retry transient JWKS / Keycloak failures with exponential backoff.

    Runs INSIDE the Keycloak circuit breaker — the circuit observes a
    single call that either succeeds or raises the final exception after
    all retries are exhausted.  Only retries on transport-layer errors;
    signature / expiry / audience errors (PyJWTError subclasses) are not
    transient and propagate immediately.
    """
    from jwt.exceptions import PyJWKClientConnectionError

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.5, max=2.0, jitter=0.25),
        retry=retry_if_exception_type(
            (PyJWKClientConnectionError, ConnectionError, TimeoutError)
        ),
        reraise=True,
    ):
        with attempt:
            return await _decode_keycloak_token_dynamic(*args, **kwargs)


class AuthService:
    """Authenticates requests via JWT or API key.

    Composes a :class:`JWTValidator` and an :class:`FGAResolver`.  The
    service owns the stateful caches (user, fund, customer, request-context)
    and orchestrates the flow: peek header → dispatch by token type → JIT
    user sync → FGA authorization → build RequestContext.
    """

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
        jwt_validator: JWTValidator | None = None,
        fga_resolver: FGAResolver | None = None,
    ) -> None:
        self._user_repo = user_repo
        self._fund_repo = fund_repo
        self._operator_repo = operator_repo
        self._api_key_repo = api_key_repo
        self._customer_repo = customer_repo
        self._servicing_edge_repo = servicing_edge_repo
        self._investor_repo = investor_repo

        # Compose helpers.  Callers may inject pre-built instances (useful
        # in tests or when sharing a resolver across services); otherwise
        # we construct defaults from the same config.
        self._jwt_validator = jwt_validator or JWTValidator(
            jwt_secret=jwt_secret,
            jwt_algorithm=jwt_algorithm,
            jwt_expiry_minutes=jwt_expiry_minutes,
            keycloak_url=keycloak_url,
            keycloak_browser_url=keycloak_browser_url,
            keycloak_realm=keycloak_realm,
            keycloak_client_id=keycloak_client_id,
            keycloak_ops_realm=keycloak_ops_realm,
            keycloak_ops_client_id=keycloak_ops_client_id,
            keycloak_investors_realm=keycloak_investors_realm,
            keycloak_investors_client_id=keycloak_investors_client_id,
        )
        self._fga_resolver = fga_resolver or FGAResolver(client=fga_client)

        # Non-FGA caches live on the orchestrator because they depend on
        # repositories the resolver does not know about.
        self._user_cache: TTLCache[str, UserRecord] = TTLCache(
            maxsize=_USER_CACHE_MAX, ttl=_USER_CACHE_TTL
        )
        self._fund_cache: TTLCache[str, FundRecord] = TTLCache(
            maxsize=_FUND_CACHE_MAX, ttl=_FUND_CACHE_TTL
        )
        self._customer_cache: TTLCache[str, CustomerRecord] = TTLCache(
            maxsize=64, ttl=120
        )
        self._ctx_cache: TTLCache[
            tuple[str, str | None, str | None], RequestContext
        ] = TTLCache(maxsize=_CTX_CACHE_MAX, ttl=_CTX_CACHE_TTL)

        # Circuit breaker around Keycloak JWKS fetches.  Tracks only network
        # / endpoint-level failures — signature-mismatch / expiry errors are
        # PyJWTError subclasses too but signal a bad token, not an unhealthy
        # upstream, so we only count the specific transport-layer subclasses
        # and plain connection / timeout errors.
        from jwt.exceptions import (
            PyJWKClientConnectionError,
            PyJWKClientError,
        )

        self._keycloak_circuit = CircuitBreaker(
            "keycloak",
            failure_threshold=5,
            recovery_timeout=30.0,
            tracked_exceptions=(
                PyJWKClientConnectionError,
                PyJWKClientError,
                ConnectionError,
                TimeoutError,
            ),
        )

    # ----- fga_client compatibility shim -----
    #
    # Tests (and some legacy internals) read/write ``self._fga_client``
    # directly.  We proxy that through to the resolver so mutations take
    # effect on both the attribute and the resolver used by orchestrator
    # code paths.

    @property
    def _fga_client(self) -> FGAClient | None:
        return self._fga_resolver.client

    @_fga_client.setter
    def _fga_client(self, value: FGAClient | None) -> None:
        self._fga_resolver.client = value

    # Expose the resolver's cache under the legacy name for test fixtures
    # that introspect ``self._fga_cache``.
    @property
    def _fga_cache(self) -> TTLCache[
        tuple[str, str, str | None], tuple[list[str], frozenset[str]]
    ]:
        return self._fga_resolver.cache

    # ----- token-hash helper (kept as static for test compat) -----

    @staticmethod
    def _token_hash(token: str) -> str:
        """Fast hash of the JWT signature (last segment) for cache keying."""
        return JWTValidator.token_hash(token)

    # ----- public JWT entry point -----

    async def authenticate_jwt(
        self,
        token: str,
        *,
        fund_slug: str | None = None,
        acting_as_customer_id: str | None = None,
    ) -> RequestContext:
        """Validate a JWT and return a RequestContext, or raise on failure.

        Detects Keycloak-issued tokens (RS256 with ``iss`` claim) vs
        app-issued tokens (HS256) and routes accordingly.
        """
        # Fast path: cached RequestContext for repeated requests
        ctx_key = (
            self._jwt_validator.token_hash(token),
            fund_slug,
            acting_as_customer_id,
        )
        cached_ctx = self._ctx_cache.get(ctx_key)
        if cached_ctx is not None:
            return cached_ctx

        header = self._jwt_validator.unverified_header(token)

        if header.get("alg") == "RS256":
            peek = self._jwt_validator.peek_rs256(token)
            issuer = peek.issuer
            ops_realm = self._jwt_validator.keycloak_ops_realm
            investors_realm = self._jwt_validator.keycloak_investors_realm
            try:
                if ops_realm and f"/realms/{ops_realm}" in issuer:
                    request_context = await self._authenticate_keycloak_operator(token)
                elif investors_realm and f"/realms/{investors_realm}" in issuer:
                    request_context = await self._authenticate_keycloak_investor(
                        token, fund_slug=fund_slug,
                    )
                else:
                    request_context = await self._authenticate_keycloak(
                        token,
                        fund_slug=fund_slug,
                        acting_as_customer_id=acting_as_customer_id,
                    )
            except CircuitOpenError as e:
                # FGA circuit opened mid-authentication — return a clean
                # error rather than leaking the internal exception.
                logger.warning("fga_circuit_open_during_auth", retry_after=e.retry_after)
                raise AuthenticationError(
                    "Authorization service temporarily unavailable",
                    code="FGA_UNAVAILABLE",
                ) from e
        else:
            # App-issued HS256 token (agent tokens, legacy)
            claims = self._jwt_validator.decode_app_token(token)
            request_context = self._claims_to_context(claims)

        self._ctx_cache[ctx_key] = request_context
        return request_context

    # ----- API key authentication -----

    async def authenticate_api_key(self, raw_key: str) -> RequestContext:
        """Validate an API key and return a RequestContext."""
        key_hash = hash_api_key(raw_key)
        record = await self._api_key_repo.get_by_hash(key_hash)
        if record is None:
            logger.warning("api_key_not_found")
            raise AuthenticationError("Invalid API key", code="INVALID_TOKEN")

        fund = await self._fund_repo.get_by_id(record.fund_id)
        if fund is None or fund.status != FundStatus.ACTIVE:
            logger.warning("api_key_fund_inactive", fund_id=record.fund_id)
            raise AuthorizationError(
                "Fund inactive or not found", code="FUND_INACTIVE"
            )

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

    # ----- token issuance (delegated to JWTValidator) -----

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
        return self._jwt_validator.create_token(
            actor_id=actor_id,
            actor_type=actor_type,
            fund_slug=fund_slug,
            fund_id=fund_id,
            customer_id=customer_id,
            roles=roles,
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
        if not self._jwt_validator.keycloak_url:
            logger.warning("keycloak_not_configured")
            raise AuthenticationError(
                "Identity provider not configured", code="IDP_UNAVAILABLE"
            )

        # Resolve realm — respects acting-as delegation.
        realm, client_id = self._jwt_validator.resolve_fund_realm(
            acting_as_customer_id
        )

        try:
            kc_claims = await self._keycloak_circuit.call(
                _decode_keycloak_token_with_retry,
                token,
                keycloak_url=self._jwt_validator.keycloak_url,
                realm=realm,
                client_id=client_id,
                keycloak_browser_url=self._jwt_validator.keycloak_browser_url,
            )
        except CircuitOpenError as e:
            logger.warning("keycloak_circuit_open", retry_after=e.retry_after)
            raise AuthenticationError(
                "Identity provider temporarily unavailable",
                code="IDP_UNAVAILABLE",
            ) from e
        except Exception as e:
            # ``decode_keycloak_token`` may raise PyJWTError (or its subclasses)
            # but we catch broadly to accommodate wrapped errors / test doubles.
            from jwt import PyJWTError

            if not isinstance(e, PyJWTError):
                raise
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
            raise AuthorizationError(
                "User account is inactive", code="USER_INACTIVE"
            )

        # Resolve fund + roles from FGA
        if fund_slug is None:
            # No fund specified — discover from FGA
            if self._fga_client is None:
                logger.warning("fga_not_available_for_fund_discovery")
                raise AuthenticationError(
                    "Authorization service unavailable",
                    code="FGA_UNAVAILABLE",
                )
            fund_ids = await self._fga_resolver.list_user_fund_ids(user.id)
            if not fund_ids:
                logger.warning("keycloak_user_no_fund_access", user_id=user.id)
                raise AuthorizationError("No fund access", code="NO_FUND_ACCESS")
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
        roles, permissions = await self._resolve_fund_access(
            user.id, fund_id, getattr(fund, "customer_id", None),
        )
        if not roles and not permissions:
            logger.warning(
                "keycloak_user_no_fund_role", user_id=user.id, fund_slug=fund_slug
            )
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
            # Fund-admin user acting on a client customer's fund — delegated
            # access.  Verify a servicing edge exists.
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
        """Delegate to the FGA resolver — kept as a method so existing tests
        and callers that invoke ``svc._resolve_fund_access`` keep working.
        """
        return await self._fga_resolver.resolve_fund_access(
            user_id, fund_id, fund_customer_id
        )

    # ----- Keycloak investor authentication -----

    async def _authenticate_keycloak_investor(
        self,
        token: str,
        *,
        fund_slug: str | None,
    ) -> RequestContext:
        """Validate a Keycloak RS256 JWT from the investors realm."""
        if not self._jwt_validator.keycloak_url:
            raise AuthenticationError(
                "Identity provider not configured", code="IDP_UNAVAILABLE"
            )
        if self._investor_repo is None:
            raise AuthenticationError(
                "Investor auth not configured", code="IDP_UNAVAILABLE"
            )

        try:
            kc_claims = await self._keycloak_circuit.call(
                _decode_keycloak_token_with_retry,
                token,
                keycloak_url=self._jwt_validator.keycloak_url,
                realm=self._jwt_validator.keycloak_investors_realm,
                client_id=self._jwt_validator.keycloak_investors_client_id,
                keycloak_browser_url=self._jwt_validator.keycloak_browser_url,
            )
        except CircuitOpenError as e:
            logger.warning("keycloak_circuit_open", retry_after=e.retry_after)
            raise AuthenticationError(
                "Identity provider temporarily unavailable",
                code="IDP_UNAVAILABLE",
            ) from e
        except Exception as e:
            from jwt import PyJWTError

            if not isinstance(e, PyJWTError):
                raise
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
            logger.warning(
                "investor_keycloak_sub_not_found",
                sub=kc_claims.sub,
                email=kc_claims.email,
            )
            raise AuthorizationError(
                "Investor account not found", code="INVESTOR_NOT_FOUND"
            )
        if not investor.is_active:
            raise AuthorizationError(
                "Investor account is inactive", code="USER_INACTIVE"
            )

        # Resolve fund — investor must specify which fund they want to view,
        # or we pick the first fund they have a capital account in.
        investor_fund_slug = fund_slug
        investor_fund_id: str | None = None
        fund_customer_id: str | None = None
        if investor_fund_slug:
            fund = await self._fund_repo.get_by_slug(investor_fund_slug)
            if fund is None or fund.status != FundStatus.ACTIVE:
                raise AuthorizationError(
                    "Fund not found", code="FUND_NOT_FOUND"
                )
            investor_fund_id = fund.id
            fund_customer_id = getattr(fund, "customer_id", None)

            # Verify investor has FGA access to this fund
            if self._fga_client is not None:
                has_access = await self._fga_resolver.check_investor_fund(
                    investor.id, investor_fund_id
                )
                if not has_access:
                    raise AuthorizationError(
                        "Fund not found", code="FUND_NOT_FOUND"
                    )
        else:
            # Discover funds from FGA
            if self._fga_client is not None:
                fund_ids = await self._fga_resolver.list_investor_fund_ids(
                    investor.id
                )
                if fund_ids:
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
        if not self._jwt_validator.keycloak_url:
            logger.warning("keycloak_not_configured")
            raise AuthenticationError(
                "Identity provider not configured", code="IDP_UNAVAILABLE"
            )

        try:
            kc_claims = await self._keycloak_circuit.call(
                _decode_keycloak_token_with_retry,
                token,
                keycloak_url=self._jwt_validator.keycloak_url,
                realm=self._jwt_validator.keycloak_ops_realm,
                client_id=self._jwt_validator.keycloak_ops_client_id,
                keycloak_browser_url=self._jwt_validator.keycloak_browser_url,
            )
        except CircuitOpenError as e:
            logger.warning("keycloak_circuit_open", retry_after=e.retry_after)
            raise AuthenticationError(
                "Identity provider temporarily unavailable",
                code="IDP_UNAVAILABLE",
            ) from e
        except Exception as e:
            from jwt import PyJWTError

            if not isinstance(e, PyJWTError):
                raise
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
            raise AuthorizationError(
                "Operator account is inactive", code="USER_INACTIVE"
            )

        # Resolve platform role from FGA
        platform_roles = await self._fga_resolver.list_platform_roles(operator.id)

        if not platform_roles:
            logger.warning("operator_no_platform_role", operator_id=operator.id)
            raise AuthorizationError(
                "No platform role assigned", code="NO_PLATFORM_ROLE"
            )

        # Use highest privilege role
        platform_role = (
            "ops_admin" if "ops_admin" in platform_roles else platform_roles[0]
        )

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
        self._fga_resolver.invalidate(user_id, fund_id)
        # Also clear context cache — roles/permissions may have changed.
        self._ctx_cache.clear()

    # ----- Public helper API -----

    async def get_user_funds(
        self, user_id: str, *, actor_type: ActorType = ActorType.USER
    ) -> list[FundInfo]:
        """Return funds the user/investor has access to (for /me/funds endpoint)."""
        if self._fga_client is None:
            return []

        if actor_type == ActorType.INVESTOR:
            fund_ids = await self._fga_resolver.list_investor_fund_ids(user_id)
        else:
            fund_ids = await self._fga_resolver.list_user_fund_ids(user_id)

        result: list[FundInfo] = []
        for fund_id in fund_ids:
            fund = await self._fund_repo.get_by_id(fund_id)
            if fund is None or fund.status != FundStatus.ACTIVE:
                continue
            if actor_type == ActorType.INVESTOR:
                role = "investor"
            else:
                roles, _perms = await self._resolve_fund_access(
                    user_id, fund_id, fund.customer_id
                )
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

    async def issue_user_token(
        self, email: str, fund_slug: str
    ) -> tuple[str, str, list[str]]:
        """Validate a user + fund access and return (token, fund_slug, roles).

        Raises ValueError with a human-readable message on failure.
        """
        user = await self._user_repo.get_by_email(email)
        if user is None or not user.is_active:
            raise ValueError("Unknown or inactive user")

        fund = await self._fund_repo.get_by_slug(fund_slug)
        if fund is None:
            raise ValueError(f"Fund not found: {fund_slug}")

        roles, _perms = await self._resolve_fund_access(
            user.id, fund.id, fund.customer_id
        )
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
        """Translate app-issued HS256 claims into a RequestContext."""
        return self._jwt_validator.claims_to_context(claims)
