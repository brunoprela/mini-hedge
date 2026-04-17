"""Unit tests for UserAdminService — platform user CRUD."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.platform.services.user import UserAdminService
from app.shared.auth.request_context import ActorType, RequestContext
from app.shared.errors import NotFoundError, ValidationError


def _make_ctx() -> RequestContext:
    return RequestContext(actor_id="op-1", actor_type=ActorType.OPERATOR)


def _make_user_record(
    user_id: str = "u-1",
    email: str = "alice@example.com",
    name: str = "Alice",
    is_active: bool = True,
) -> MagicMock:
    r = MagicMock()
    r.id = user_id
    r.email = email
    r.name = name
    r.is_active = is_active
    return r


def _make_service(
    existing_user: MagicMock | None = None,
) -> tuple[UserAdminService, AsyncMock, AsyncMock]:
    user_repo = AsyncMock()
    user_repo.list_paginated = AsyncMock(return_value=([], 0))
    user_repo.get_by_email = AsyncMock(return_value=existing_user)
    user_repo.get_by_id = AsyncMock(return_value=None)
    async def _insert_with_id(record, **kw):
        if not record.id:
            record.id = "generated-id"

    user_repo.insert = AsyncMock(side_effect=_insert_with_id)
    user_repo.update = AsyncMock(return_value=None)

    audit_repo = AsyncMock()
    audit_repo.insert_admin_event = AsyncMock()

    svc = UserAdminService(user_repo=user_repo, audit_repo=audit_repo)
    return svc, user_repo, audit_repo


class TestListUsers:
    @pytest.mark.asyncio
    async def test_returns_paginated(self) -> None:
        svc, user_repo, _ = _make_service()
        records = [_make_user_record("u1", "a@x.com", "A"), _make_user_record("u2", "b@x.com", "B")]
        user_repo.list_paginated = AsyncMock(return_value=(records, 2))

        result = await svc.list_users(limit=50, offset=0)

        assert result.total == 2
        assert len(result.items) == 2
        assert result.items[0].email == "a@x.com"

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        svc, _, _ = _make_service()
        result = await svc.list_users()
        assert result.items == []


class TestCreateUser:
    @pytest.mark.asyncio
    async def test_creates_and_audits(self) -> None:
        svc, user_repo, audit_repo = _make_service()

        result = await svc.create_user(
            email="new@example.com", name="New User", request_context=_make_ctx(),
        )

        assert result.email == "new@example.com"
        assert result.name == "New User"
        assert result.is_active is True
        user_repo.insert.assert_called_once()
        audit_repo.insert_admin_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_email_raises(self) -> None:
        existing = _make_user_record(email="taken@x.com")
        svc, _, _ = _make_service(existing_user=existing)

        with pytest.raises(ValidationError, match="email already exists"):
            await svc.create_user(
                email="taken@x.com", name="Dup", request_context=_make_ctx(),
            )


class TestGetUser:
    @pytest.mark.asyncio
    async def test_returns_user(self) -> None:
        svc, user_repo, _ = _make_service()
        user_repo.get_by_id = AsyncMock(return_value=_make_user_record("u-1"))

        result = await svc.get_user("u-1")

        assert result.id == "u-1"
        assert result.name == "Alice"

    @pytest.mark.asyncio
    async def test_not_found_raises(self) -> None:
        svc, _, _ = _make_service()

        with pytest.raises(NotFoundError):
            await svc.get_user("missing")


class TestUpdateUser:
    @pytest.mark.asyncio
    async def test_updates_and_audits(self) -> None:
        svc, user_repo, audit_repo = _make_service()
        updated = _make_user_record("u-1", name="Alice Updated")
        user_repo.update = AsyncMock(return_value=updated)

        from app.modules.platform.interfaces.user import UpdateUserRequest

        result = await svc.update_user("u-1", UpdateUserRequest(name="Alice Updated"), request_context=_make_ctx())

        assert result.name == "Alice Updated"
        audit_repo.insert_admin_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_not_found_raises(self) -> None:
        svc, _, _ = _make_service()

        from app.modules.platform.interfaces.user import UpdateUserRequest

        with pytest.raises(NotFoundError):
            await svc.update_user("missing", UpdateUserRequest(name="X"), request_context=_make_ctx())
