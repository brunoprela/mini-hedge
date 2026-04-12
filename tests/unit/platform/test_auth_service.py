"""Unit tests for AuthService — JWT auth, API key auth, token issuance, FGA cache."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

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


def _make_api_key_record(
    fund_id: str = "fund-1",
    roles: list[str] | None = None,
    actor_type: str = "agent",
) -> MagicMock:
    r = MagicMock()
    r.id = "key-1"
    r.fund_id = fund_id
    r.roles = roles or ["viewer"]
    r.actor_type = actor_type
    return r


def _make_service(
    user: MagicMock | None = None,
    fund: MagicMock | None = None,
    operator: MagicMock | None = None,
    api_key_record: MagicMock | None = None,
    fga_relations: list[str] | None = None,
    fga_objects: list[str] | None = None,
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
    api_key_repo.get_by_hash = AsyncMock(return_value=api_key_record)

    fga_client = AsyncMock()
    fga_client.list_relations = AsyncMock(return_value=fga_relations or [])
    fga_client.list_objects = AsyncMock(return_value=fga_objects or [])

    return AuthService(
        user_repo=user_repo,
        fund_repo=fund_repo,
        operator_repo=operator_repo,
        api_key_repo=api_key_repo,
        fga_client=fga_client,
        jwt_secret="test-secret-key-32chars-minimum!",
        jwt_algorithm="HS256",
        jwt_expiry_minutes=60,
    )


class TestCreateToken:
    def test_creates_valid_token(self) -> None:
        svc = _make_service()
        token = svc.create_token(
            actor_id="u-1",
            actor_type=ActorType.USER,
            fund_slug="alpha",
            fund_id="fund-1",
            roles=["admin"],
        )
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_with_delegation(self) -> None:
        svc = _make_service()
        token = svc.create_token(
            actor_id="agent-1",
            actor_type=ActorType.AGENT,
            fund_slug="alpha",
            fund_id="fund-1",
            roles=["viewer"],
            delegated_by="u-1",
        )
        assert isinstance(token, str)


class TestAuthenticateJWT:
    @pytest.mark.asyncio
    async def test_hs256_token_roundtrip(self) -> None:
        svc = _make_service()
        token = svc.create_token(
            actor_id="u-1",
            actor_type=ActorType.USER,
            fund_slug="alpha",
            fund_id="fund-1",
            roles=["admin"],
        )

        ctx = await svc.authenticate_jwt(token)

        assert ctx.actor_id == "u-1"
        assert ctx.fund_slug == "alpha"
        assert "admin" in ctx.roles

    @pytest.mark.asyncio
    async def test_invalid_token_raises(self) -> None:
        svc = _make_service()

        with pytest.raises(AuthenticationError):
            await svc.authenticate_jwt("not.a.valid.jwt")

    @pytest.mark.asyncio
    async def test_context_cache_hit(self) -> None:
        svc = _make_service()
        token = svc.create_token(
            actor_id="u-1",
            actor_type=ActorType.USER,
            fund_slug="alpha",
            fund_id="fund-1",
            roles=["admin"],
        )

        ctx1 = await svc.authenticate_jwt(token)
        ctx2 = await svc.authenticate_jwt(token)

        assert ctx1.actor_id == ctx2.actor_id


class TestAuthenticateApiKey:
    @pytest.mark.asyncio
    async def test_valid_api_key(self) -> None:
        fund = _make_fund()
        api_key = _make_api_key_record(fund_id="fund-1")
        svc = _make_service(fund=fund, api_key_record=api_key)

        ctx = await svc.authenticate_api_key("raw-key-value")

        assert ctx.actor_id == "key-1"
        assert ctx.actor_type == ActorType.AGENT
        assert ctx.fund_slug == "alpha"

    @pytest.mark.asyncio
    async def test_unknown_api_key(self) -> None:
        svc = _make_service(api_key_record=None)

        with pytest.raises(AuthenticationError):
            await svc.authenticate_api_key("unknown-key")

    @pytest.mark.asyncio
    async def test_inactive_fund_api_key(self) -> None:
        fund = _make_fund(status=FundStatus.INACTIVE)
        api_key = _make_api_key_record(fund_id="fund-1")
        svc = _make_service(fund=fund, api_key_record=api_key)

        with pytest.raises(AuthorizationError):
            await svc.authenticate_api_key("raw-key")

    @pytest.mark.asyncio
    async def test_fund_not_found_api_key(self) -> None:
        api_key = _make_api_key_record(fund_id="fund-1")
        svc = _make_service(fund=None, api_key_record=api_key)

        with pytest.raises(AuthorizationError):
            await svc.authenticate_api_key("raw-key")


class TestIssueUserToken:
    @pytest.mark.asyncio
    async def test_issue_token_success(self) -> None:
        user = _make_user()
        fund = _make_fund()
        svc = _make_service(user=user, fund=fund, fga_relations=["admin"])

        token, slug, roles = await svc.issue_user_token("alice@example.com", "alpha")

        assert isinstance(token, str)
        assert slug == "alpha"
        assert "admin" in roles

    @pytest.mark.asyncio
    async def test_issue_token_unknown_user(self) -> None:
        svc = _make_service(user=None, fund=_make_fund())

        with pytest.raises(ValueError, match="Unknown or inactive"):
            await svc.issue_user_token("nobody@example.com", "alpha")

    @pytest.mark.asyncio
    async def test_issue_token_inactive_user(self) -> None:
        user = _make_user(is_active=False)
        svc = _make_service(user=user, fund=_make_fund())

        with pytest.raises(ValueError, match="Unknown or inactive"):
            await svc.issue_user_token("alice@example.com", "alpha")

    @pytest.mark.asyncio
    async def test_issue_token_fund_not_found(self) -> None:
        user = _make_user()
        svc = _make_service(user=user, fund=None)

        with pytest.raises(ValueError, match="Fund not found"):
            await svc.issue_user_token("alice@example.com", "nonexistent")

    @pytest.mark.asyncio
    async def test_issue_token_no_access(self) -> None:
        user = _make_user()
        fund = _make_fund()
        svc = _make_service(user=user, fund=fund, fga_relations=[])

        with pytest.raises(ValueError, match="no access"):
            await svc.issue_user_token("alice@example.com", "alpha")


class TestIssueAgentToken:
    def test_issues_agent_token(self) -> None:
        svc = _make_service()
        token = svc.issue_agent_token(
            agent_id="agent-1",
            fund_slug="alpha",
            fund_id="fund-1",
            roles=["viewer"],
            delegated_by="u-1",
        )
        assert isinstance(token, str)


class TestGetUserFunds:
    @pytest.mark.asyncio
    async def test_returns_funds(self) -> None:
        fund = _make_fund()
        svc = _make_service(fund=fund, fga_objects=["fund-1"], fga_relations=["admin"])

        result = await svc.get_user_funds("u-1")

        assert len(result) == 1
        assert result[0].fund_slug == "alpha"

    @pytest.mark.asyncio
    async def test_no_fga_client(self) -> None:
        svc = _make_service()
        svc._fga_client = None

        result = await svc.get_user_funds("u-1")

        assert result == []

    @pytest.mark.asyncio
    async def test_skips_inactive_funds(self) -> None:
        fund = _make_fund(status=FundStatus.INACTIVE)
        svc = _make_service(fund=fund, fga_objects=["fund-1"])

        result = await svc.get_user_funds("u-1")

        assert result == []


class TestFGACache:
    def test_invalidate_clears_ctx_cache(self) -> None:
        svc = _make_service()
        # Populate context cache
        svc._ctx_cache[("hash", "alpha")] = MagicMock()

        svc.invalidate_fga_cache("u-1", "fund-1")

        # Context cache should be cleared
        assert len(svc._ctx_cache) == 0

    @pytest.mark.asyncio
    async def test_resolve_fund_access_caches(self) -> None:
        svc = _make_service(fga_relations=["admin"])

        r1 = await svc._resolve_fund_access("u-1", "fund-1")
        r2 = await svc._resolve_fund_access("u-1", "fund-1")

        assert r1 == r2
        # FGA should only be called once
        svc._fga_client.list_relations.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_fund_access_no_fga(self) -> None:
        svc = _make_service()
        svc._fga_client = None

        roles, perms = await svc._resolve_fund_access("u-1", "fund-1")

        assert roles == []
        assert perms == frozenset()
