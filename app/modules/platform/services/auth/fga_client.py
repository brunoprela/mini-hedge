"""OpenFGA permission resolution, caching, and revocation bridge.

Wraps the shared ``FGAClient`` with the platform-module specific role and
permission vocabulary (fund user roles, platform roles, fund permissions)
plus a short-lived TTL cache keyed by (user_id, fund_id, customer_id).

The actual FGA network client (``app.shared.fga.FGAClient``) is passed in
as ``client`` and may be ``None`` when FGA is disabled — in that case all
resolver methods return empty results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cachetools import TTLCache

from app.shared.auth import (
    FGA_FUND_PERMISSIONS,
    FGA_PERMISSION_MAP,
)

if TYPE_CHECKING:
    from app.shared.fga import FGAClient

# FGA relation names for fund user roles
FUND_USER_ROLES: list[str] = [
    "admin",
    "portfolio_manager",
    "analyst",
    "risk_manager",
    "compliance_officer",
    "viewer",
]
PLATFORM_ROLES: list[str] = ["ops_admin", "ops_viewer"]

# Cache key: (actor_id, fund_id, customer_id) → (roles, permissions)
_FGA_CACHE_MAX = 256
_FGA_CACHE_TTL = 30  # seconds

# Sentinel used in cache keys so that None and "" collapse to the same entry.
# Without it, a handler passing ``customer_id=None`` and one passing
# ``customer_id=""`` would cache-miss against each other even though FGA treats
# them identically (unscoped fund access).
_NO_CUSTOMER = "__none__"


def _normalize_customer_id(customer_id: str | None) -> str:
    """Map ``None`` and empty string to a single sentinel for cache keys."""
    return customer_id or _NO_CUSTOMER


class FGAResolver:
    """Platform-flavoured FGA client: resolves roles + permissions with cache.

    The wrapped ``FGAClient`` may be replaced at runtime (e.g. tests set it
    to ``None`` on the owning ``AuthService``, which proxies the change here
    via a property setter).
    """

    def __init__(self, client: FGAClient | None) -> None:
        self._client = client
        # Cache key's third element is always the normalized customer id string
        # (``_NO_CUSTOMER`` when the caller passed ``None`` or ``""``) so read
        # and write paths never disagree on the key.
        self._cache: TTLCache[
            tuple[str, str, str], tuple[list[str], frozenset[str]]
        ] = TTLCache(maxsize=_FGA_CACHE_MAX, ttl=_FGA_CACHE_TTL)

    # ----- client accessor (supports runtime mutation by tests) -----

    @property
    def client(self) -> FGAClient | None:
        return self._client

    @client.setter
    def client(self, value: FGAClient | None) -> None:
        self._client = value

    @property
    def cache(self) -> TTLCache[
        tuple[str, str, str], tuple[list[str], frozenset[str]]
    ]:
        """Direct handle for callers that need to inspect the cache."""
        return self._cache

    # ----- fund user roles + permissions -----

    async def resolve_fund_access(
        self,
        user_id: str,
        fund_id: str,
        fund_customer_id: str | None = None,
    ) -> tuple[list[str], frozenset[str]]:
        """Resolve fund user roles and permissions from FGA, with TTL cache.

        Queries FGA for both role relations (admin, analyst, ...) and
        permission relations (can_read_instruments, can_execute_trades, ...).
        FGA computes the union: permissions granted by role + direct grants.
        """
        cache_key = (user_id, fund_id, _normalize_customer_id(fund_customer_id))
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        if self._client is None:
            return [], frozenset()

        from app.shared.fga.client import qualify_object_id

        fga_object = qualify_object_id("fund", fund_id, fund_customer_id)
        # Single FGA call resolves both roles and effective permissions
        all_relations = await self._client.list_relations(
            user=f"user:{user_id}",
            object=fga_object,
            relations=FUND_USER_ROLES + FGA_FUND_PERMISSIONS,
        )

        roles_set = set(FUND_USER_ROLES)
        roles = [r for r in all_relations if r in roles_set]
        permissions = frozenset(
            FGA_PERMISSION_MAP[r] for r in all_relations if r in FGA_PERMISSION_MAP
        )

        result = (roles, permissions)
        self._cache[cache_key] = result
        return result

    # ----- fund discovery -----

    async def list_user_fund_ids(self, user_id: str) -> list[str]:
        """Return unqualified fund IDs the user can read."""
        if self._client is None:
            return []
        from app.shared.fga.client import unqualify_object_id

        qualified = await self._client.list_objects(
            user=f"user:{user_id}", relation="can_read", type="fund"
        )
        return sorted(unqualify_object_id(fid) for fid in qualified)

    async def list_investor_fund_ids(self, investor_id: str) -> list[str]:
        """Return unqualified fund IDs the investor can read."""
        if self._client is None:
            return []
        from app.shared.fga.client import unqualify_object_id

        qualified = await self._client.list_objects(
            user=f"investor:{investor_id}", relation="can_read", type="fund"
        )
        return sorted(unqualify_object_id(fid) for fid in qualified)

    async def check_investor_fund(self, investor_id: str, fund_id: str) -> bool:
        """Verify an investor has ``can_read`` on the given fund."""
        if self._client is None:
            return False
        return await self._client.check(
            user=f"investor:{investor_id}",
            relation="can_read",
            object=f"fund:{fund_id}",
        )

    # ----- platform (operator) roles -----

    async def list_platform_roles(self, operator_id: str) -> list[str]:
        """Return the operator's platform-level role relations."""
        if self._client is None:
            return []
        return await self._client.list_relations(
            user=f"operator:{operator_id}",
            object="platform:global",
            relations=PLATFORM_ROLES,
        )

    # ----- revocation bridge -----

    def invalidate(self, user_id: str, fund_id: str) -> None:
        """Evict cached role lookups for the (user, fund) pair.

        Cache keys are 3-tuples ``(user_id, fund_id, customer_id)``; all
        matching entries are evicted regardless of customer_id so access
        changes take effect immediately.
        """
        keys_to_evict = [
            k for k in self._cache if k[0] == user_id and k[1] == fund_id
        ]
        for k in keys_to_evict:
            self._cache.pop(k, None)
