"""Unit tests for AdminService — facade delegation + servicing edges."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.platform.services.admin import AdminService
from app.shared.auth.request_context import ActorType, RequestContext
from app.shared.errors import NotFoundError


def _make_request_context() -> RequestContext:
    return RequestContext(
        actor_id="op-1",
        actor_type=ActorType.OPERATOR,
        roles=frozenset(["ops_admin"]),
        permissions=frozenset(),
    )


def _make_edge_record(edge_id: str = "edge-1", **overrides) -> MagicMock:
    r = MagicMock()
    r.id = edge_id
    r.admin_customer_id = overrides.get("admin_customer_id", "cust-admin")
    r.client_customer_id = overrides.get("client_customer_id", "cust-client")
    r.scoped_roles = overrides.get("scoped_roles", ["viewer"])
    return r


def _make_service(
    with_servicing_edge_repo: bool = True,
    with_customer_repo: bool = False,
) -> AdminService:
    user_repo = AsyncMock()
    operator_repo = AsyncMock()
    fund_repo = AsyncMock()
    fga_client = AsyncMock()
    fga_client.read_tuples = AsyncMock(return_value=[])
    fga_client.write_tuples = AsyncMock()
    fga_client.delete_tuples = AsyncMock()
    audit_repo = AsyncMock()
    audit_repo.insert_admin_event = AsyncMock()
    audit_repo.query = AsyncMock(return_value=([], 0))

    customer_repo = AsyncMock() if with_customer_repo else None
    servicing_edge_repo = AsyncMock() if with_servicing_edge_repo else None
    if servicing_edge_repo:
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


class TestServicingEdges:
    @pytest.mark.asyncio
    async def test_create_servicing_edge(self) -> None:
        svc = _make_service()

        result = await svc.create_servicing_edge(
            admin_customer_id="cust-admin",
            client_customer_id="cust-client",
            scoped_roles=["viewer", "trader"],
        )

        svc._servicing_edge_repo.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_by_admin(self) -> None:
        svc = _make_service()
        svc._servicing_edge_repo.get_client_customers = AsyncMock(
            return_value=[_make_edge_record()]
        )

        result = await svc.list_servicing_edges(admin_customer_id="cust-admin")

        assert len(result) == 1
        svc._servicing_edge_repo.get_client_customers.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_by_client(self) -> None:
        svc = _make_service()
        svc._servicing_edge_repo.get_admin_customers = AsyncMock(
            return_value=[_make_edge_record()]
        )

        result = await svc.list_servicing_edges(client_customer_id="cust-client")

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_no_filter_returns_empty(self) -> None:
        svc = _make_service()

        result = await svc.list_servicing_edges()

        assert result == []

    @pytest.mark.asyncio
    async def test_update_roles(self) -> None:
        edge = _make_edge_record()
        svc = _make_service()
        svc._servicing_edge_repo.update_scoped_roles = AsyncMock(return_value=edge)

        result = await svc.update_servicing_edge_roles("edge-1", ["admin"])

        assert result.id == "edge-1"

    @pytest.mark.asyncio
    async def test_update_roles_not_found(self) -> None:
        svc = _make_service()

        with pytest.raises(NotFoundError):
            await svc.update_servicing_edge_roles("nonexistent", ["admin"])

    @pytest.mark.asyncio
    async def test_suspend_edge(self) -> None:
        edge = _make_edge_record()
        svc = _make_service()
        svc._servicing_edge_repo.suspend = AsyncMock(return_value=edge)

        result = await svc.suspend_servicing_edge("edge-1")

        assert result.id == "edge-1"

    @pytest.mark.asyncio
    async def test_suspend_not_found(self) -> None:
        svc = _make_service()

        with pytest.raises(NotFoundError):
            await svc.suspend_servicing_edge("nonexistent")

    @pytest.mark.asyncio
    async def test_terminate_edge(self) -> None:
        edge = _make_edge_record()
        svc = _make_service()
        svc._servicing_edge_repo.terminate = AsyncMock(return_value=edge)

        result = await svc.terminate_servicing_edge("edge-1")

        assert result.id == "edge-1"

    @pytest.mark.asyncio
    async def test_terminate_not_found(self) -> None:
        svc = _make_service()

        with pytest.raises(NotFoundError):
            await svc.terminate_servicing_edge("nonexistent")


class TestDelegation:
    """Verify the facade delegates to the correct sub-service."""

    @pytest.mark.asyncio
    async def test_list_audit_delegates(self) -> None:
        svc = _make_service()

        page = await svc.list_audit(fund_slug="test-fund")

        assert page.total == 0

    @pytest.mark.asyncio
    async def test_list_fund_access_delegates(self) -> None:
        svc = _make_service()

        grants = await svc.list_fund_access("fund-1")

        # Returns empty list since no tuples
        assert isinstance(grants, list)
