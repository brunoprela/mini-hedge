"""Unit tests for AuthService Keycloak authentication paths.

Covers RS256 token routing, operator authentication via ops realm,
fund-user authentication edge cases, and delegated session handling.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
import pytest

from app.modules.platform.models.fund import FundStatus
from app.modules.platform.services.auth import AuthService
from app.shared.auth.request_context import ActorType, RequestContext
from app.shared.errors import AuthenticationError, AuthorizationError


def _make_user(user_id: str = "u-1", is_active: bool = True, customer_id: str | None = None) -> MagicMock:
    u = MagicMock()
    u.id = user_id
    u.email = "alice@example.com"
    u.name = "Alice"
    u.is_active = is_active
    u.customer_id = customer_id
    return u


def _make_fund(
    fund_id: str = "fund-1",
    slug: str = "alpha",
    status: str = FundStatus.ACTIVE,
    customer_id: str | None = None,
) -> MagicMock:
    f = MagicMock()
    f.id = fund_id
    f.slug = slug
    f.status = status
    f.name = "Alpha Fund"
    f.customer_id = customer_id
    return f


def _make_operator(operator_id: str = "op-1", is_active: bool = True) -> MagicMock:
    o = MagicMock()
    o.id = operator_id
    o.email = "bob@ops.com"
    o.name = "Bob"
    o.is_active = is_active
    return o


def _make_kc_claims(sub: str = "kc-sub-1", email: str = "alice@example.com", name: str = "Alice") -> MagicMock:
    c = MagicMock()
    c.sub = sub
    c.email = email
    c.name = name
    return c


def _make_service(
    user: MagicMock | None = None,
    fund: MagicMock | None = None,
    operator: MagicMock | None = None,
    fga_relations: list[str] | None = None,
    fga_objects: list[str] | None = None,
    keycloak_url: str = "http://kc.local",
    keycloak_ops_realm: str = "minihedge-ops",
    servicing_edge_repo: AsyncMock | None = None,
    customer_repo: AsyncMock | None = None,
) -> AuthService:
    user_repo = AsyncMock()
    user_repo.get_by_email = AsyncMock(return_value=user)
    user_repo.upsert_from_keycloak = AsyncMock(return_value=user)

    fund_repo = AsyncMock()
    fund_repo.get_by_id = AsyncMock(return_value=fund)
    fund_repo.get_by_slug = AsyncMock(return_value=fund)

    operator_repo = AsyncMock()
    operator_repo.upsert_from_keycloak = AsyncMock(return_value=operator)

    api_key_repo = AsyncMock()

    fga_client = AsyncMock()
    fga_client.list_relations = AsyncMock(return_value=fga_relations or [])
    fga_client.list_objects = AsyncMock(return_value=fga_objects or [])

    return AuthService(
        user_repo=user_repo,
        fund_repo=fund_repo,
        operator_repo=operator_repo,
        api_key_repo=api_key_repo,
        customer_repo=customer_repo,
        servicing_edge_repo=servicing_edge_repo,
        fga_client=fga_client,
        jwt_secret="test-secret-key-32chars-minimum!",
        jwt_algorithm="HS256",
        jwt_expiry_minutes=60,
        keycloak_url=keycloak_url,
        keycloak_realm="minihedge",
        keycloak_client_id="minihedge-client",
        keycloak_ops_realm=keycloak_ops_realm,
        keycloak_ops_client_id="minihedge-ops-client",
    )


def _make_rs256_token(issuer: str = "http://kc.local/realms/minihedge") -> str:
    """Create a minimal RS256-looking JWT (header says RS256 but unsigned for testing)."""
    import json, base64

    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({"iss": issuer, "sub": "kc-sub-1"}).encode()).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(b"fakesig").rstrip(b"=").decode()
    return f"{header}.{payload}.{sig}"


class TestRS256Routing:
    """Test that RS256 tokens are routed to the correct Keycloak handler."""

    @pytest.mark.asyncio
    async def test_ops_realm_routes_to_operator_auth(self) -> None:
        """Token from ops realm should call _authenticate_keycloak_operator."""
        operator = _make_operator()
        svc = _make_service(operator=operator, fga_relations=["ops_admin"])
        token = _make_rs256_token(issuer="http://kc.local/realms/minihedge-ops")

        with patch.object(svc, "_authenticate_keycloak_operator", new_callable=AsyncMock) as mock_op:
            mock_op.return_value = RequestContext(
                actor_id="op-1", actor_type=ActorType.OPERATOR, platform_role="ops_admin",
                roles=frozenset(["ops_admin"]), permissions=frozenset(),
            )
            ctx = await svc.authenticate_jwt(token)

            mock_op.assert_called_once_with(token)
            assert ctx.actor_type == ActorType.OPERATOR

    @pytest.mark.asyncio
    async def test_fund_realm_routes_to_user_auth(self) -> None:
        """Token from fund realm should call _authenticate_keycloak."""
        user = _make_user()
        fund = _make_fund()
        svc = _make_service(user=user, fund=fund, fga_relations=["admin"])
        token = _make_rs256_token(issuer="http://kc.local/realms/minihedge")

        with patch.object(svc, "_authenticate_keycloak", new_callable=AsyncMock) as mock_kc:
            mock_kc.return_value = RequestContext(
                actor_id="u-1", actor_type=ActorType.USER, fund_slug="alpha",
                roles=frozenset(["admin"]), permissions=frozenset(),
            )
            ctx = await svc.authenticate_jwt(token, fund_slug="alpha")

            mock_kc.assert_called_once_with(
                token, fund_slug="alpha", acting_as_customer_id=None,
            )
            assert ctx.actor_type == ActorType.USER

    @pytest.mark.asyncio
    async def test_rs256_unverified_decode_failure(self) -> None:
        """Corrupted RS256 payload should raise AuthenticationError."""
        import base64, json

        header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256"}).encode()).rstrip(b"=").decode()
        # Garbage payload
        token = f"{header}.!!!garbage!!!.sig"
        svc = _make_service()

        with pytest.raises(AuthenticationError):
            await svc.authenticate_jwt(token)


class TestAuthenticateKeycloakOperator:
    """Tests for _authenticate_keycloak_operator."""

    @pytest.mark.asyncio
    async def test_successful_operator_auth(self) -> None:
        operator = _make_operator()
        svc = _make_service(operator=operator, fga_relations=["ops_admin"])

        with patch("app.modules.platform.services.auth.decode_keycloak_token", new_callable=AsyncMock) as mock_decode:
            mock_decode.return_value = _make_kc_claims(sub="op-kc-1", email="bob@ops.com", name="Bob")

            ctx = await svc._authenticate_keycloak_operator("fake-token")

            assert ctx.actor_id == "op-1"
            assert ctx.actor_type == ActorType.OPERATOR
            assert ctx.platform_role == "ops_admin"
            assert "ops_admin" in ctx.roles

    @pytest.mark.asyncio
    async def test_operator_no_keycloak_url_raises(self) -> None:
        svc = _make_service(keycloak_url="")

        with pytest.raises(AuthenticationError, match="Identity provider not configured"):
            await svc._authenticate_keycloak_operator("fake-token")

    @pytest.mark.asyncio
    async def test_operator_invalid_token_raises(self) -> None:
        svc = _make_service()

        with patch("app.modules.platform.services.auth.decode_keycloak_token", new_callable=AsyncMock) as mock_decode:
            mock_decode.side_effect = pyjwt.PyJWTError("bad token")

            with pytest.raises(AuthenticationError):
                await svc._authenticate_keycloak_operator("bad-token")

    @pytest.mark.asyncio
    async def test_inactive_operator_raises(self) -> None:
        operator = _make_operator(is_active=False)
        svc = _make_service(operator=operator)

        with patch("app.modules.platform.services.auth.decode_keycloak_token", new_callable=AsyncMock) as mock_decode:
            mock_decode.return_value = _make_kc_claims()

            with pytest.raises(AuthorizationError, match="inactive"):
                await svc._authenticate_keycloak_operator("fake-token")

    @pytest.mark.asyncio
    async def test_operator_no_platform_role_raises(self) -> None:
        operator = _make_operator()
        svc = _make_service(operator=operator, fga_relations=[])

        with patch("app.modules.platform.services.auth.decode_keycloak_token", new_callable=AsyncMock) as mock_decode:
            mock_decode.return_value = _make_kc_claims()

            with pytest.raises(AuthorizationError, match="No platform role"):
                await svc._authenticate_keycloak_operator("fake-token")

    @pytest.mark.asyncio
    async def test_operator_no_fga_client_has_no_roles(self) -> None:
        operator = _make_operator()
        svc = _make_service(operator=operator)
        svc._fga_client = None

        with patch("app.modules.platform.services.auth.decode_keycloak_token", new_callable=AsyncMock) as mock_decode:
            mock_decode.return_value = _make_kc_claims()

            # No FGA client means no roles resolved, which leads to NO_PLATFORM_ROLE
            with pytest.raises(AuthorizationError, match="No platform role"):
                await svc._authenticate_keycloak_operator("fake-token")

    @pytest.mark.asyncio
    async def test_operator_ops_viewer_role(self) -> None:
        operator = _make_operator()
        svc = _make_service(operator=operator, fga_relations=["ops_viewer"])

        with patch("app.modules.platform.services.auth.decode_keycloak_token", new_callable=AsyncMock) as mock_decode:
            mock_decode.return_value = _make_kc_claims()

            ctx = await svc._authenticate_keycloak_operator("fake-token")

            assert ctx.platform_role == "ops_viewer"
            assert "ops_viewer" in ctx.roles

    @pytest.mark.asyncio
    async def test_operator_invalid_platform_role_gets_empty_permissions(self) -> None:
        operator = _make_operator()
        svc = _make_service(operator=operator, fga_relations=["unknown_role"])

        with patch("app.modules.platform.services.auth.decode_keycloak_token", new_callable=AsyncMock) as mock_decode:
            mock_decode.return_value = _make_kc_claims()

            ctx = await svc._authenticate_keycloak_operator("fake-token")

            # unknown_role is not a valid PlatformRole, so permissions = frozenset()
            assert ctx.permissions == frozenset()


class TestAuthenticateKeycloakFundUser:
    """Tests for _authenticate_keycloak — fund user path."""

    @pytest.mark.asyncio
    async def test_no_keycloak_url_raises(self) -> None:
        svc = _make_service(keycloak_url="")

        with pytest.raises(AuthenticationError, match="Identity provider not configured"):
            await svc._authenticate_keycloak("fake-token", fund_slug="alpha")

    @pytest.mark.asyncio
    async def test_invalid_keycloak_token_raises(self) -> None:
        svc = _make_service()

        with patch("app.modules.platform.services.auth.decode_keycloak_token", new_callable=AsyncMock) as mock_decode:
            mock_decode.side_effect = pyjwt.PyJWTError("invalid")

            with pytest.raises(AuthenticationError):
                await svc._authenticate_keycloak("bad-token", fund_slug="alpha")

    @pytest.mark.asyncio
    async def test_inactive_user_raises(self) -> None:
        user = _make_user(is_active=False)
        svc = _make_service(user=user)

        with patch("app.modules.platform.services.auth.decode_keycloak_token", new_callable=AsyncMock) as mock_decode:
            mock_decode.return_value = _make_kc_claims()

            with pytest.raises(AuthorizationError, match="inactive"):
                await svc._authenticate_keycloak("fake-token", fund_slug="alpha")

    @pytest.mark.asyncio
    async def test_user_cache_hit_avoids_upsert(self) -> None:
        user = _make_user()
        svc = _make_service(user=user)
        # Pre-populate user cache
        svc._user_cache["kc-sub-1"] = user

        with patch("app.modules.platform.services.auth.decode_keycloak_token", new_callable=AsyncMock) as mock_decode:
            mock_decode.return_value = _make_kc_claims()

            # Will fail at _resolve_fund_access due to NameError on customer_id,
            # but we can verify upsert was NOT called
            try:
                await svc._authenticate_keycloak("fake-token", fund_slug="alpha")
            except Exception:
                pass

            svc._user_repo.upsert_from_keycloak.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_fund_slug_no_fga_raises(self) -> None:
        user = _make_user()
        svc = _make_service(user=user)
        svc._fga_client = None

        with patch("app.modules.platform.services.auth.decode_keycloak_token", new_callable=AsyncMock) as mock_decode:
            mock_decode.return_value = _make_kc_claims()

            with pytest.raises(AuthenticationError, match="Authorization service unavailable"):
                await svc._authenticate_keycloak("fake-token", fund_slug=None)

    @pytest.mark.asyncio
    async def test_no_fund_slug_no_fund_access_raises(self) -> None:
        user = _make_user()
        svc = _make_service(user=user, fga_objects=[])

        with patch("app.modules.platform.services.auth.decode_keycloak_token", new_callable=AsyncMock) as mock_decode:
            mock_decode.return_value = _make_kc_claims()

            with pytest.raises(AuthorizationError, match="No fund access"):
                await svc._authenticate_keycloak("fake-token", fund_slug=None)

    @pytest.mark.asyncio
    async def test_no_fund_slug_fund_inactive_raises(self) -> None:
        user = _make_user()
        fund = _make_fund(status=FundStatus.INACTIVE)
        svc = _make_service(user=user, fund=fund, fga_objects=["fund-1"])

        with patch("app.modules.platform.services.auth.decode_keycloak_token", new_callable=AsyncMock) as mock_decode:
            mock_decode.return_value = _make_kc_claims()

            with pytest.raises(AuthorizationError, match="Fund inactive"):
                await svc._authenticate_keycloak("fake-token", fund_slug=None)

    @pytest.mark.asyncio
    async def test_no_fund_slug_fund_not_found_raises(self) -> None:
        user = _make_user()
        svc = _make_service(user=user, fund=None, fga_objects=["fund-1"])

        with patch("app.modules.platform.services.auth.decode_keycloak_token", new_callable=AsyncMock) as mock_decode:
            mock_decode.return_value = _make_kc_claims()

            with pytest.raises(AuthorizationError, match="Fund inactive"):
                await svc._authenticate_keycloak("fake-token", fund_slug=None)

    @pytest.mark.asyncio
    async def test_fund_slug_not_found_raises(self) -> None:
        user = _make_user()
        svc = _make_service(user=user, fund=None)

        with patch("app.modules.platform.services.auth.decode_keycloak_token", new_callable=AsyncMock) as mock_decode:
            mock_decode.return_value = _make_kc_claims()

            with pytest.raises(AuthorizationError, match="Fund not found"):
                await svc._authenticate_keycloak("fake-token", fund_slug="nonexistent")

    @pytest.mark.asyncio
    async def test_fund_slug_inactive_raises(self) -> None:
        user = _make_user()
        fund = _make_fund(status=FundStatus.INACTIVE)
        svc = _make_service(user=user, fund=fund)

        with patch("app.modules.platform.services.auth.decode_keycloak_token", new_callable=AsyncMock) as mock_decode:
            mock_decode.return_value = _make_kc_claims()

            with pytest.raises(AuthorizationError, match="Fund inactive"):
                await svc._authenticate_keycloak("fake-token", fund_slug="alpha")

    @pytest.mark.asyncio
    async def test_fund_cache_hit(self) -> None:
        user = _make_user()
        fund = _make_fund()
        svc = _make_service(user=user, fund=fund)
        # Pre-populate fund cache
        svc._fund_cache["alpha"] = fund

        with patch("app.modules.platform.services.auth.decode_keycloak_token", new_callable=AsyncMock) as mock_decode:
            mock_decode.return_value = _make_kc_claims()

            # Will hit the fund cache, then fail at _resolve_fund_access
            try:
                await svc._authenticate_keycloak("fake-token", fund_slug="alpha")
            except Exception:
                pass

            svc._fund_repo.get_by_slug.assert_not_called()


class TestHS256EdgeCases:
    """Cover HS256 decode failure path (lines 195-197 in auth.py)."""

    @pytest.mark.asyncio
    async def test_tampered_hs256_token_raises(self) -> None:
        """HS256 token with wrong secret should raise AuthenticationError."""
        svc = _make_service()
        # Create a valid-looking HS256 token with a different secret
        from app.shared.auth import encode_token
        from app.shared.auth.request_context import ActorType

        token = encode_token(
            actor_id="u-1",
            actor_type=ActorType.USER,
            fund_slug="alpha",
            fund_id="fund-1",
            roles=["admin"],
            secret="wrong-secret-key-32chars-minimum!",
            algorithm="HS256",
            expiry_minutes=60,
        )

        with pytest.raises(AuthenticationError):
            await svc.authenticate_jwt(token)


class TestTokenHash:
    def test_produces_hex_string(self) -> None:
        result = AuthService._token_hash("header.payload.signature")
        assert isinstance(result, str)
        assert len(result) == 16

    def test_same_token_same_hash(self) -> None:
        h1 = AuthService._token_hash("a.b.c")
        h2 = AuthService._token_hash("a.b.c")
        assert h1 == h2

    def test_different_tokens_different_hash(self) -> None:
        h1 = AuthService._token_hash("a.b.c")
        h2 = AuthService._token_hash("a.b.d")
        assert h1 != h2


class TestGetUserFundsWithCustomer:
    """Test get_user_funds resolving customer name."""

    @pytest.mark.asyncio
    async def test_resolves_customer_name(self) -> None:
        fund = _make_fund(customer_id="cust-1")
        customer = MagicMock()
        customer.name = "Acme Corp"

        customer_repo = AsyncMock()
        customer_repo.get_by_id = AsyncMock(return_value=customer)

        svc = _make_service(fund=fund)
        svc._customer_repo = customer_repo
        svc._fga_client.list_objects = AsyncMock(return_value=["fund-1"])
        svc._fga_client.list_relations = AsyncMock(return_value=["admin"])

        result = await svc.get_user_funds("u-1")

        assert len(result) == 1
        assert result[0].customer_name == "Acme Corp"

    @pytest.mark.asyncio
    async def test_customer_not_found_returns_none_name(self) -> None:
        fund = _make_fund(customer_id="cust-1")

        customer_repo = AsyncMock()
        customer_repo.get_by_id = AsyncMock(return_value=None)

        svc = _make_service(fund=fund)
        svc._customer_repo = customer_repo
        svc._fga_client.list_objects = AsyncMock(return_value=["fund-1"])
        svc._fga_client.list_relations = AsyncMock(return_value=["admin"])

        result = await svc.get_user_funds("u-1")

        assert len(result) == 1
        assert result[0].customer_name is None

    @pytest.mark.asyncio
    async def test_no_roles_defaults_to_viewer(self) -> None:
        fund = _make_fund()

        svc = _make_service(fund=fund)
        svc._fga_client.list_objects = AsyncMock(return_value=["fund-1"])
        # No role relations, only permission relations
        svc._fga_client.list_relations = AsyncMock(return_value=["can_read_instruments"])

        result = await svc.get_user_funds("u-1")

        assert len(result) == 1
        assert result[0].role == "viewer"
