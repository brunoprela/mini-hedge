"""Unit tests for AccessGrantService — fund access management via FGA."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.platform.services.access import AccessGrantService
from app.shared.auth.request_context import ActorType, RequestContext
from app.shared.errors import NotFoundError


def _make_request_context(
    actor_id: str = "user-1",
    actor_type: ActorType = ActorType.OPERATOR,
) -> RequestContext:
    return RequestContext(
        actor_id=actor_id,
        actor_type=actor_type,
        roles=frozenset(["ops_admin"]),
        permissions=frozenset(),
    )


def _make_fund_record(fund_id: str = "fund-1", slug: str = "test-fund", customer_id: str | None = None) -> MagicMock:
    r = MagicMock()
    r.id = fund_id
    r.slug = slug
    r.customer_id = customer_id
    return r


def _make_user_record(user_id: str = "user-1", name: str = "Alice") -> MagicMock:
    r = MagicMock()
    r.id = user_id
    r.name = name
    return r


def _make_operator_record(operator_id: str = "op-1", name: str = "Bob Ops") -> MagicMock:
    r = MagicMock()
    r.id = operator_id
    r.name = name
    return r


def _make_service(
    fund: MagicMock | None = None,
    user: MagicMock | None = None,
    operator: MagicMock | None = None,
    fga_tuples: list | None = None,
    audit_records: list | None = None,
    audit_total: int = 0,
    with_auth_service: bool = False,
) -> AccessGrantService:
    user_repo = AsyncMock()
    user_repo.get_by_id = AsyncMock(return_value=user)

    operator_repo = AsyncMock()
    operator_repo.get_by_id = AsyncMock(return_value=operator)

    fund_repo = AsyncMock()
    fund_repo.get_by_id = AsyncMock(return_value=fund)

    fga_client = AsyncMock()
    fga_client.read_tuples = AsyncMock(return_value=fga_tuples or [])
    fga_client.write_tuples = AsyncMock()
    fga_client.delete_tuples = AsyncMock()

    audit_repo = AsyncMock()
    audit_repo.insert_admin_event = AsyncMock()
    audit_repo.query = AsyncMock(return_value=(audit_records or [], audit_total))

    auth_service = MagicMock() if with_auth_service else None
    if auth_service:
        auth_service.invalidate_fga_cache = MagicMock()

    return AccessGrantService(
        user_repo=user_repo,
        operator_repo=operator_repo,
        fund_repo=fund_repo,
        fga_client=fga_client,
        audit_repo=audit_repo,
        auth_service=auth_service,
    )


class TestListFundAccess:
    @pytest.mark.asyncio
    async def test_lists_user_and_operator_grants(self) -> None:
        fund = _make_fund_record()
        user = _make_user_record("u-1", "Alice")
        operator = _make_operator_record("op-1", "Bob Ops")
        tuples = [
            ("user:u-1", "admin", "fund:fund-1"),
            ("operator:op-1", "ops_full", "fund:fund-1"),
        ]
        svc = _make_service(fund=fund, user=user, operator=operator, fga_tuples=tuples)

        grants = await svc.list_fund_access("fund-1")

        assert len(grants) == 2
        user_grant = next(g for g in grants if g.user_type == "user")
        assert user_grant.user_id == "u-1"
        assert user_grant.relation == "admin"
        assert user_grant.display_name == "Alice"

    @pytest.mark.asyncio
    async def test_permission_relation_type(self) -> None:
        fund = _make_fund_record()
        tuples = [("user:u-1", "can_read_instruments", "fund:fund-1")]
        svc = _make_service(fund=fund, user=_make_user_record("u-1"), fga_tuples=tuples)

        grants = await svc.list_fund_access("fund-1")

        assert grants[0].relation_type == "permission"

    @pytest.mark.asyncio
    async def test_skips_non_user_operator_tuples(self) -> None:
        fund = _make_fund_record()
        tuples = [("group:admins", "admin", "fund:fund-1")]
        svc = _make_service(fund=fund, fga_tuples=tuples)

        grants = await svc.list_fund_access("fund-1")

        assert len(grants) == 0

    @pytest.mark.asyncio
    async def test_no_fund_customer_id(self) -> None:
        fund = _make_fund_record(customer_id=None)
        svc = _make_service(fund=fund, fga_tuples=[])

        grants = await svc.list_fund_access("fund-1")

        assert grants == []


class TestGrantAccess:
    @pytest.mark.asyncio
    async def test_grant_user_access(self) -> None:
        fund = _make_fund_record()
        user = _make_user_record("u-1")
        svc = _make_service(fund=fund, user=user, with_auth_service=True)
        ctx = _make_request_context()

        await svc.grant_access("fund-1", user_type="user", user_id="u-1", relation="admin", request_context=ctx)

        svc._fga_client.write_tuples.assert_called_once()
        svc._audit_repo.insert_admin_event.assert_called_once()
        svc._auth_service.invalidate_fga_cache.assert_called_once_with("u-1", "fund-1")

    @pytest.mark.asyncio
    async def test_grant_operator_access(self) -> None:
        fund = _make_fund_record()
        operator = _make_operator_record("op-1")
        svc = _make_service(fund=fund, operator=operator)
        ctx = _make_request_context()

        await svc.grant_access("fund-1", user_type="operator", user_id="op-1", relation="ops_full", request_context=ctx)

        svc._fga_client.write_tuples.assert_called_once()

    @pytest.mark.asyncio
    async def test_grant_fund_not_found(self) -> None:
        svc = _make_service(fund=None)
        ctx = _make_request_context()

        with pytest.raises(NotFoundError):
            await svc.grant_access("nonexistent", user_type="user", user_id="u-1", relation="admin", request_context=ctx)

    @pytest.mark.asyncio
    async def test_grant_user_not_found(self) -> None:
        fund = _make_fund_record()
        svc = _make_service(fund=fund, user=None)
        ctx = _make_request_context()

        with pytest.raises(NotFoundError):
            await svc.grant_access("fund-1", user_type="user", user_id="nonexistent", relation="admin", request_context=ctx)

    @pytest.mark.asyncio
    async def test_grant_operator_not_found(self) -> None:
        fund = _make_fund_record()
        svc = _make_service(fund=fund, operator=None)
        ctx = _make_request_context()

        with pytest.raises(NotFoundError):
            await svc.grant_access("fund-1", user_type="operator", user_id="nonexistent", relation="ops_full", request_context=ctx)

    @pytest.mark.asyncio
    async def test_no_auth_service_skips_cache_invalidation(self) -> None:
        fund = _make_fund_record()
        user = _make_user_record("u-1")
        svc = _make_service(fund=fund, user=user, with_auth_service=False)
        ctx = _make_request_context()

        await svc.grant_access("fund-1", user_type="user", user_id="u-1", relation="admin", request_context=ctx)

        svc._fga_client.write_tuples.assert_called_once()


class TestRevokeAccess:
    @pytest.mark.asyncio
    async def test_revoke_user_access(self) -> None:
        fund = _make_fund_record()
        svc = _make_service(fund=fund, with_auth_service=True)
        ctx = _make_request_context()

        await svc.revoke_access("fund-1", user_type="user", user_id="u-1", relation="admin", request_context=ctx)

        svc._fga_client.delete_tuples.assert_called_once()
        svc._audit_repo.insert_admin_event.assert_called_once()
        svc._auth_service.invalidate_fga_cache.assert_called_once_with("u-1", "fund-1")

    @pytest.mark.asyncio
    async def test_revoke_fund_not_found(self) -> None:
        svc = _make_service(fund=None)
        ctx = _make_request_context()

        with pytest.raises(NotFoundError):
            await svc.revoke_access("nonexistent", user_type="user", user_id="u-1", relation="admin", request_context=ctx)

    @pytest.mark.asyncio
    async def test_revoke_operator_no_cache_invalidation(self) -> None:
        """Operator revocation should not invalidate user FGA cache."""
        fund = _make_fund_record()
        svc = _make_service(fund=fund, with_auth_service=True)
        ctx = _make_request_context()

        await svc.revoke_access("fund-1", user_type="operator", user_id="op-1", relation="ops_full", request_context=ctx)

        svc._fga_client.delete_tuples.assert_called_once()
        svc._auth_service.invalidate_fga_cache.assert_not_called()


class TestListAudit:
    @pytest.mark.asyncio
    async def test_returns_audit_page(self) -> None:
        record = MagicMock()
        record.id = "audit-1"
        record.event_id = "evt-1"
        record.event_type = "admin.access_granted"
        record.actor_id = "user-1"
        record.actor_type = "operator"
        record.fund_slug = "test-fund"
        record.payload = {"relation": "admin"}
        record.created_at = datetime.now(timezone.utc)

        svc = _make_service(audit_records=[record], audit_total=1)

        page = await svc.list_audit(fund_slug="test-fund")

        assert page.total == 1
        assert len(page.items) == 1
        assert page.items[0].event_type == "admin.access_granted"

    @pytest.mark.asyncio
    async def test_empty_audit(self) -> None:
        svc = _make_service()
        page = await svc.list_audit()
        assert page.total == 0
        assert page.items == []
