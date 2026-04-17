"""Unit tests for CustomerAdminService — customer CRUD with audit logging."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.platform.services.customer import CustomerAdminService
from app.shared.auth.request_context import ActorType, RequestContext
from app.shared.errors import NotFoundError, ValidationError


def _make_ctx() -> RequestContext:
    return RequestContext(actor_id="op-1", actor_type=ActorType.OPERATOR)


def _make_customer_record(
    customer_id: str = "cust-1",
    slug: str = "acme",
    name: str = "Acme Fund",
    customer_type: str = "direct_fund",
    status: str = "active",
) -> MagicMock:
    r = MagicMock()
    r.id = customer_id
    r.slug = slug
    r.name = name
    r.customer_type = customer_type
    r.status = status
    return r


def _make_service(
    existing_by_slug: MagicMock | None = None,
    existing_by_id: MagicMock | None = None,
) -> tuple[CustomerAdminService, AsyncMock, AsyncMock]:
    customer_repo = AsyncMock()
    customer_repo.list_paginated = AsyncMock(return_value=([], 0))
    customer_repo.get_by_slug = AsyncMock(return_value=existing_by_slug)
    customer_repo.get_by_id = AsyncMock(return_value=existing_by_id)
    async def _insert_with_defaults(record, **kw):
        if record.id is None:
            record.id = "generated-id"
        if record.status is None:
            record.status = "active"

    customer_repo.insert = AsyncMock(side_effect=_insert_with_defaults)
    customer_repo.update = AsyncMock(return_value=None)

    audit_repo = AsyncMock()
    audit_repo.insert_admin_event = AsyncMock()

    svc = CustomerAdminService(customer_repo=customer_repo, audit_repo=audit_repo)
    return svc, customer_repo, audit_repo


class TestListCustomers:
    @pytest.mark.asyncio
    async def test_returns_paginated(self) -> None:
        svc, repo, _ = _make_service()
        records = [
            _make_customer_record("c1", "alpha", "Alpha"),
            _make_customer_record("c2", "beta", "Beta"),
        ]
        repo.list_paginated = AsyncMock(return_value=(records, 2))

        result = await svc.list_customers(limit=50, offset=0)

        assert result.total == 2
        assert len(result.items) == 2
        assert result.items[0].slug == "alpha"
        assert result.items[1].slug == "beta"
        assert result.limit == 50
        assert result.offset == 0

    @pytest.mark.asyncio
    async def test_empty_list(self) -> None:
        svc, _, _ = _make_service()

        result = await svc.list_customers()

        assert result.total == 0
        assert result.items == []


class TestCreateCustomer:
    @pytest.mark.asyncio
    async def test_creates_and_audits(self) -> None:
        svc, repo, audit_repo = _make_service()
        ctx = _make_ctx()

        result = await svc.create_customer(
            slug="new-co",
            name="New Company",
            customer_type="direct_fund",
            request_context=ctx,
        )

        assert result.slug == "new-co"
        assert result.name == "New Company"
        assert result.customer_type == "direct_fund"
        repo.insert.assert_called_once()
        audit_repo.insert_admin_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_slug_raises(self) -> None:
        existing = _make_customer_record(slug="taken")
        svc, _, _ = _make_service(existing_by_slug=existing)
        ctx = _make_ctx()

        with pytest.raises(ValidationError, match="slug already exists"):
            await svc.create_customer(
                slug="taken",
                name="Dup",
                customer_type="direct_fund",
                request_context=ctx,
            )

    @pytest.mark.asyncio
    async def test_audit_payload_contains_details(self) -> None:
        svc, _, audit_repo = _make_service()
        ctx = _make_ctx()

        await svc.create_customer(
            slug="audited",
            name="Audited Co",
            customer_type="fund_administrator",
            request_context=ctx,
        )

        call_kwargs = audit_repo.insert_admin_event.call_args.kwargs
        assert call_kwargs["actor_id"] == "op-1"
        assert call_kwargs["payload"]["slug"] == "audited"
        assert call_kwargs["payload"]["customer_type"] == "fund_administrator"


class TestGetCustomer:
    @pytest.mark.asyncio
    async def test_returns_customer(self) -> None:
        record = _make_customer_record("cust-1")
        svc, _, _ = _make_service(existing_by_id=record)

        result = await svc.get_customer("cust-1")

        assert result.id == "cust-1"
        assert result.name == "Acme Fund"

    @pytest.mark.asyncio
    async def test_not_found_raises(self) -> None:
        svc, _, _ = _make_service()

        with pytest.raises(NotFoundError):
            await svc.get_customer("missing")


class TestUpdateCustomer:
    @pytest.mark.asyncio
    async def test_updates_and_audits(self) -> None:
        updated = _make_customer_record("cust-1", name="Updated Name")
        svc, repo, audit_repo = _make_service()
        repo.update = AsyncMock(return_value=updated)
        ctx = _make_ctx()

        from app.modules.platform.interfaces.customer import UpdateCustomerRequest

        result = await svc.update_customer(
            "cust-1",
            UpdateCustomerRequest(name="Updated Name"),
            request_context=ctx,
        )

        assert result.name == "Updated Name"
        audit_repo.insert_admin_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_not_found_raises(self) -> None:
        svc, repo, _ = _make_service()
        repo.update = AsyncMock(return_value=None)
        ctx = _make_ctx()

        from app.modules.platform.interfaces.customer import UpdateCustomerRequest

        with pytest.raises(NotFoundError):
            await svc.update_customer(
                "missing",
                UpdateCustomerRequest(name="X"),
                request_context=ctx,
            )

    @pytest.mark.asyncio
    async def test_audit_contains_changes(self) -> None:
        updated = _make_customer_record("cust-1", name="New Name", status="inactive")
        svc, repo, audit_repo = _make_service()
        repo.update = AsyncMock(return_value=updated)
        ctx = _make_ctx()

        from app.modules.platform.interfaces.customer import UpdateCustomerRequest

        await svc.update_customer(
            "cust-1",
            UpdateCustomerRequest(name="New Name", status="inactive"),
            request_context=ctx,
        )

        call_kwargs = audit_repo.insert_admin_event.call_args.kwargs
        assert call_kwargs["payload"]["customer_id"] == "cust-1"
        assert "changes" in call_kwargs["payload"]
