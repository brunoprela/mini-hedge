"""Unit tests for AdminService facade — customer delegation paths.

The admin facade delegates to sub-services. The user/operator/fund/access
delegation is already tested via test_admin_service.py. This file covers
the customer delegation paths (lines 252-293 in admin.py).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.platform.services.admin import AdminService
from app.shared.auth.request_context import ActorType, RequestContext


def _make_ctx() -> RequestContext:
    return RequestContext(
        actor_id="op-1",
        actor_type=ActorType.OPERATOR,
        roles=frozenset(["ops_admin"]),
        permissions=frozenset(),
    )


def _make_customer_info(cid: str = "cust-1", slug: str = "acme", name: str = "Acme") -> MagicMock:
    from app.modules.platform.interfaces.customer import CustomerInfo

    return CustomerInfo(id=cid, slug=slug, name=name, customer_type="direct_fund", status="active")


def _make_service_with_customers() -> AdminService:
    user_repo = AsyncMock()
    user_repo.list_paginated = AsyncMock(return_value=([], 0))
    user_repo.get_by_email = AsyncMock(return_value=None)
    user_repo.get_by_id = AsyncMock(return_value=None)

    async def _user_insert_with_id(record, **kw):
        if not record.id:
            record.id = "generated-user-id"

    user_repo.insert = AsyncMock(side_effect=_user_insert_with_id)
    user_repo.update = AsyncMock(return_value=None)

    operator_repo = AsyncMock()
    operator_repo.list_paginated = AsyncMock(return_value=([], 0))
    operator_repo.get_by_email = AsyncMock(return_value=None)
    operator_repo.get_by_id = AsyncMock(return_value=None)

    async def _op_insert_with_id(record, **kw):
        if not record.id:
            record.id = "generated-op-id"

    operator_repo.insert = AsyncMock(side_effect=_op_insert_with_id)
    operator_repo.update = AsyncMock(return_value=None)
    fund_repo = AsyncMock()
    fund_repo.list_paginated = AsyncMock(return_value=([], 0))
    fund_repo.get_by_slug = AsyncMock(return_value=None)
    fund_repo.update = AsyncMock(return_value=None)

    async def _fund_insert_with_defaults(record, **kw):
        if not record.id:
            record.id = "generated-fund-id"

    fund_repo.insert = AsyncMock(side_effect=_fund_insert_with_defaults)

    fga_client = AsyncMock()
    fga_client.read_tuples = AsyncMock(return_value=[])
    fga_client.write_tuples = AsyncMock()
    fga_client.delete_tuples = AsyncMock()
    audit_repo = AsyncMock()
    audit_repo.insert_admin_event = AsyncMock()
    audit_repo.query = AsyncMock(return_value=([], 0))

    async def _customer_insert_with_defaults(record, **kw):
        """Simulate server_default behaviour for id and status."""
        if record.id is None:
            record.id = "generated-cust-id"
        if record.status is None:
            record.status = "active"

    customer_repo = AsyncMock()
    customer_repo.list_paginated = AsyncMock(return_value=([], 0))
    customer_repo.get_by_slug = AsyncMock(return_value=None)
    customer_repo.get_by_id = AsyncMock(return_value=None)
    customer_repo.insert = AsyncMock(side_effect=_customer_insert_with_defaults)
    customer_repo.update = AsyncMock(return_value=None)

    servicing_edge_repo = AsyncMock()
    servicing_edge_repo.insert = AsyncMock()
    servicing_edge_repo.get_client_customers = AsyncMock(return_value=[])
    servicing_edge_repo.get_admin_customers = AsyncMock(return_value=[])
    servicing_edge_repo.update_scoped_roles = AsyncMock(return_value=None)
    servicing_edge_repo.suspend = AsyncMock(return_value=None)
    servicing_edge_repo.terminate = AsyncMock(return_value=None)

    return AdminService(
        user_repo=user_repo,
        operator_repo=operator_repo,
        fund_repo=fund_repo,
        customer_repo=customer_repo,
        servicing_edge_repo=servicing_edge_repo,
        fga_client=fga_client,
        audit_repo=audit_repo,
    )


class TestCustomerDelegation:
    @pytest.mark.asyncio
    async def test_list_customers_delegates(self) -> None:
        svc = _make_service_with_customers()

        result = await svc.list_customers(limit=10, offset=0)

        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_create_customer_delegates(self) -> None:
        svc = _make_service_with_customers()
        ctx = _make_ctx()

        result = await svc.create_customer(
            slug="new-cust",
            name="New Customer",
            customer_type="direct_fund",
            request_context=ctx,
        )

        assert result.slug == "new-cust"

    @pytest.mark.asyncio
    async def test_get_customer_not_found(self) -> None:
        svc = _make_service_with_customers()

        from app.shared.errors import NotFoundError

        with pytest.raises(NotFoundError):
            await svc.get_customer("missing-id")

    @pytest.mark.asyncio
    async def test_update_customer_not_found(self) -> None:
        svc = _make_service_with_customers()
        ctx = _make_ctx()

        from app.modules.platform.interfaces.customer import UpdateCustomerRequest
        from app.shared.errors import NotFoundError

        with pytest.raises(NotFoundError):
            await svc.update_customer(
                "missing-id",
                UpdateCustomerRequest(name="X"),
                request_context=ctx,
            )


class TestFundDelegation:
    @pytest.mark.asyncio
    async def test_list_funds_delegates(self) -> None:
        svc = _make_service_with_customers()

        result = await svc.list_funds(limit=25, offset=5)

        assert result.total == 0

    @pytest.mark.asyncio
    async def test_create_fund_delegates(self) -> None:
        svc = _make_service_with_customers()
        ctx = _make_ctx()

        result = await svc.create_fund(
            slug="new-fund",
            name="New Fund",
            base_currency="USD",
            request_context=ctx,
        )

        assert result.slug == "new-fund"

    @pytest.mark.asyncio
    async def test_update_fund_not_found(self) -> None:
        svc = _make_service_with_customers()
        ctx = _make_ctx()

        from app.modules.platform.interfaces.fund import UpdateFundRequest
        from app.shared.errors import NotFoundError

        with pytest.raises(NotFoundError):
            await svc.update_fund("missing", UpdateFundRequest(name="X"), request_context=ctx)


class TestUserDelegation:
    @pytest.mark.asyncio
    async def test_list_users_delegates(self) -> None:
        svc = _make_service_with_customers()

        result = await svc.list_users(limit=50, offset=10)

        assert result.total == 0

    @pytest.mark.asyncio
    async def test_create_user_delegates(self) -> None:
        svc = _make_service_with_customers()
        ctx = _make_ctx()

        result = await svc.create_user(
            email="new@example.com",
            name="New User",
            request_context=ctx,
        )

        assert result.email == "new@example.com"

    @pytest.mark.asyncio
    async def test_get_user_not_found(self) -> None:
        svc = _make_service_with_customers()

        from app.shared.errors import NotFoundError

        with pytest.raises(NotFoundError):
            await svc.get_user("missing")

    @pytest.mark.asyncio
    async def test_update_user_not_found(self) -> None:
        svc = _make_service_with_customers()
        ctx = _make_ctx()

        from app.modules.platform.interfaces.user import UpdateUserRequest
        from app.shared.errors import NotFoundError

        with pytest.raises(NotFoundError):
            await svc.update_user("missing", UpdateUserRequest(name="X"), request_context=ctx)


class TestOperatorDelegation:
    @pytest.mark.asyncio
    async def test_list_operators_delegates(self) -> None:
        svc = _make_service_with_customers()

        result = await svc.list_operators(limit=20, offset=0)

        assert result.total == 0

    @pytest.mark.asyncio
    async def test_create_operator_delegates(self) -> None:
        svc = _make_service_with_customers()
        ctx = _make_ctx()

        result = await svc.create_operator(
            email="ops@example.com",
            name="Ops User",
            platform_role="ops_viewer",
            request_context=ctx,
        )

        assert result.email == "ops@example.com"


class TestAccessDelegation:
    @pytest.mark.asyncio
    async def test_grant_access_delegates(self) -> None:
        svc = _make_service_with_customers()
        ctx = _make_ctx()
        # fund must exist for grant_access
        svc._access_service._fund_repo.get_by_id = AsyncMock(return_value=MagicMock(id="f1", slug="s", customer_id=None))
        svc._access_service._user_repo.get_by_id = AsyncMock(return_value=MagicMock(id="u1", name="A"))

        await svc.grant_access(
            "f1", user_type="user", user_id="u1", relation="admin", request_context=ctx,
        )

    @pytest.mark.asyncio
    async def test_revoke_access_delegates(self) -> None:
        svc = _make_service_with_customers()
        ctx = _make_ctx()
        svc._access_service._fund_repo.get_by_id = AsyncMock(return_value=MagicMock(id="f1", slug="s", customer_id=None))

        await svc.revoke_access(
            "f1", user_type="user", user_id="u1", relation="admin", request_context=ctx,
        )

    @pytest.mark.asyncio
    async def test_list_audit_with_filters(self) -> None:
        svc = _make_service_with_customers()

        page = await svc.list_audit(
            fund_slug="alpha",
            event_type="order.created",
            actor_id="user-1",
            entity_type="order",
            entity_id="ord-1",
            correlation_id="corr-1",
            limit=50,
            offset=10,
        )

        assert page.total == 0
