"""Unit tests for OperatorAdminService — operator CRUD with FGA role management."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.platform.services.operator import OperatorAdminService
from app.shared.auth.request_context import ActorType, RequestContext
from app.shared.errors import NotFoundError, ValidationError


def _make_ctx() -> RequestContext:
    return RequestContext(actor_id="admin-1", actor_type=ActorType.OPERATOR)


def _make_operator_record(
    op_id: str = "op-1",
    email: str = "ops@example.com",
    name: str = "Ops User",
    is_active: bool = True,
) -> MagicMock:
    r = MagicMock()
    r.id = op_id
    r.email = email
    r.name = name
    r.is_active = is_active
    return r


def _make_service(
    existing_operator: MagicMock | None = None,
) -> tuple[OperatorAdminService, AsyncMock, AsyncMock, AsyncMock]:
    operator_repo = AsyncMock()
    operator_repo.list_paginated = AsyncMock(return_value=([], 0))
    operator_repo.get_by_email = AsyncMock(return_value=existing_operator)
    operator_repo.get_by_id = AsyncMock(return_value=None)
    async def _insert_with_id(record, **kw):
        if not record.id:
            record.id = "generated-id"

    operator_repo.insert = AsyncMock(side_effect=_insert_with_id)
    operator_repo.update = AsyncMock(return_value=None)

    fga_client = AsyncMock()
    fga_client.list_relations = AsyncMock(return_value=[])
    fga_client.write_tuples = AsyncMock()
    fga_client.delete_tuples = AsyncMock()

    audit_repo = AsyncMock()
    audit_repo.insert_admin_event = AsyncMock()

    svc = OperatorAdminService(
        operator_repo=operator_repo,
        fga_client=fga_client,
        audit_repo=audit_repo,
    )
    return svc, operator_repo, fga_client, audit_repo


class TestListOperators:
    @pytest.mark.asyncio
    async def test_returns_operators_with_roles(self) -> None:
        svc, op_repo, fga, _ = _make_service()
        records = [_make_operator_record("op-1")]
        op_repo.list_paginated = AsyncMock(return_value=(records, 1))
        fga.list_relations = AsyncMock(return_value=["ops_admin"])

        result = await svc.list_operators()

        assert result.total == 1
        assert result.items[0].platform_role == "ops_admin"

    @pytest.mark.asyncio
    async def test_viewer_role_when_no_admin(self) -> None:
        svc, op_repo, fga, _ = _make_service()
        records = [_make_operator_record("op-1")]
        op_repo.list_paginated = AsyncMock(return_value=(records, 1))
        fga.list_relations = AsyncMock(return_value=["ops_viewer"])

        result = await svc.list_operators()

        assert result.items[0].platform_role == "ops_viewer"

    @pytest.mark.asyncio
    async def test_no_role_when_empty_relations(self) -> None:
        svc, op_repo, fga, _ = _make_service()
        records = [_make_operator_record("op-1")]
        op_repo.list_paginated = AsyncMock(return_value=(records, 1))
        fga.list_relations = AsyncMock(return_value=[])

        result = await svc.list_operators()

        assert result.items[0].platform_role is None


class TestCreateOperator:
    @pytest.mark.asyncio
    async def test_creates_with_fga_role(self) -> None:
        svc, op_repo, fga, audit_repo = _make_service()

        result = await svc.create_operator(
            email="new@example.com",
            name="New Ops",
            platform_role="ops_admin",
            request_context=_make_ctx(),
        )

        assert result.email == "new@example.com"
        assert result.platform_role == "ops_admin"
        op_repo.insert.assert_called_once()
        fga.write_tuples.assert_called_once()
        audit_repo.insert_admin_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_email_raises(self) -> None:
        existing = _make_operator_record(email="taken@x.com")
        svc, _, _, _ = _make_service(existing_operator=existing)

        with pytest.raises(ValidationError, match="email already exists"):
            await svc.create_operator(
                email="taken@x.com",
                name="Dup",
                platform_role="ops_viewer",
                request_context=_make_ctx(),
            )


class TestUpdateOperator:
    @pytest.mark.asyncio
    async def test_updates_name(self) -> None:
        svc, op_repo, fga, audit_repo = _make_service()
        updated = _make_operator_record("op-1", name="Updated Name")
        op_repo.update = AsyncMock(return_value=updated)
        fga.list_relations = AsyncMock(return_value=["ops_viewer"])

        from app.modules.platform.interfaces.operator import UpdateOperatorRequest

        result = await svc.update_operator(
            "op-1", UpdateOperatorRequest(name="Updated Name"), request_context=_make_ctx(),
        )

        assert result.name == "Updated Name"
        audit_repo.insert_admin_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_role_change_removes_old_and_adds_new(self) -> None:
        svc, op_repo, fga, _ = _make_service()
        record = _make_operator_record("op-1")
        op_repo.update = AsyncMock(return_value=record)
        # First call: old roles lookup; second call: update calls list_relations again for response
        fga.list_relations = AsyncMock(side_effect=[["ops_viewer"], ["ops_admin"]])

        from app.modules.platform.interfaces.operator import UpdateOperatorRequest

        result = await svc.update_operator(
            "op-1",
            UpdateOperatorRequest(platform_role="ops_admin"),
            request_context=_make_ctx(),
        )

        fga.delete_tuples.assert_called_once()  # removes old role
        fga.write_tuples.assert_called_once()  # adds new role
        assert result.platform_role == "ops_admin"

    @pytest.mark.asyncio
    async def test_not_found_raises(self) -> None:
        svc, op_repo, _, _ = _make_service()
        op_repo.update = AsyncMock(return_value=None)
        op_repo.get_by_id = AsyncMock(return_value=None)

        from app.modules.platform.interfaces.operator import UpdateOperatorRequest

        with pytest.raises(NotFoundError):
            await svc.update_operator(
                "missing", UpdateOperatorRequest(name="X"), request_context=_make_ctx(),
            )
