"""Unit tests for platform repositories — all repo methods via mocked AsyncSession.

Each repository method receives an explicit session, so BaseRepository._session()
just yields it back without creating a new one. We mock the session's execute(),
add(), commit(), refresh() methods to verify correct queries are built.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.platform.models.customer import CustomerRecord
from app.modules.platform.models.fund import FundRecord, FundStatus
from app.modules.platform.models.operator import OperatorRecord
from app.modules.platform.models.user import UserRecord
from app.modules.platform.repositories.api_key import APIKeyRepository
from app.modules.platform.repositories.audit import AuditLogRepository
from app.modules.platform.repositories.customer import CustomerRepository
from app.modules.platform.repositories.fund import FundRepository
from app.modules.platform.repositories.operator import OperatorRepository
from app.modules.platform.repositories.portfolio import PortfolioRepository
from app.modules.platform.repositories.servicing_edge import ServicingEdgeRepository
from app.modules.platform.repositories.user import UserRepository


def _mock_session() -> AsyncMock:
    """Create a mock AsyncSession that works with the _session() context manager."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _mock_session_factory() -> AsyncMock:
    return AsyncMock()


def _scalar_result(value):
    """Mock a result whose .scalar_one_or_none() returns value."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalar_one.return_value = value
    result.scalars.return_value.all.return_value = [value] if value else []
    return result


def _scalars_result(values: list):
    """Mock a result whose .scalars().all() returns a list."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


def _count_then_list(count: int, records: list):
    """Return two execute results: first for count, second for list query."""
    count_result = MagicMock()
    count_result.scalar_one.return_value = count

    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = records

    return [count_result, list_result]


# ========================== FundRepository ==========================

class TestFundRepository:
    def _make_repo(self) -> FundRepository:
        return FundRepository(session_factory=_mock_session_factory())

    @pytest.mark.asyncio
    async def test_get_by_id(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        fund = MagicMock(spec=FundRecord)
        session.execute.return_value = _scalar_result(fund)

        result = await repo.get_by_id("fund-1", session=session)

        assert result is fund
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        session.execute.return_value = _scalar_result(None)

        result = await repo.get_by_id("missing", session=session)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_slug(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        fund = MagicMock(spec=FundRecord)
        session.execute.return_value = _scalar_result(fund)

        result = await repo.get_by_slug("alpha", session=session)

        assert result is fund

    @pytest.mark.asyncio
    async def test_get_all_active(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        funds = [MagicMock(spec=FundRecord), MagicMock(spec=FundRecord)]
        session.execute.return_value = _scalars_result(funds)

        result = await repo.get_all_active(session=session)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_all(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        funds = [MagicMock(spec=FundRecord)]
        session.execute.return_value = _scalars_result(funds)

        result = await repo.get_all(session=session)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_all_paginated(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        funds = [MagicMock(spec=FundRecord)]
        session.execute.side_effect = _count_then_list(5, funds)

        result, total = await repo.get_all_paginated(limit=10, offset=0, session=session)

        assert total == 5
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_insert(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        record = MagicMock(spec=FundRecord)

        await repo.insert(record, session=session)

        session.add.assert_called_once_with(record)
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        fund = MagicMock(spec=FundRecord)
        # First execute: update statement; second: select to return
        session.execute.side_effect = [MagicMock(), _scalar_result(fund)]

        from app.modules.platform.interfaces.fund import UpdateFundRequest

        result = await repo.update("fund-1", UpdateFundRequest(name="New"), session=session)

        assert result is fund
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_empty_values(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        fund = MagicMock(spec=FundRecord)
        session.execute.return_value = _scalar_result(fund)

        from app.modules.platform.interfaces.fund import UpdateFundRequest

        result = await repo.update("fund-1", UpdateFundRequest(), session=session)

        assert result is fund
        # No commit needed for empty update, just the select
        session.execute.assert_called_once()


# ========================== CustomerRepository ==========================

class TestCustomerRepository:
    def _make_repo(self) -> CustomerRepository:
        return CustomerRepository(session_factory=_mock_session_factory())

    @pytest.mark.asyncio
    async def test_get_by_id(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        customer = MagicMock(spec=CustomerRecord)
        session.execute.return_value = _scalar_result(customer)

        result = await repo.get_by_id("cust-1", session=session)

        assert result is customer

    @pytest.mark.asyncio
    async def test_get_by_slug(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        customer = MagicMock(spec=CustomerRecord)
        session.execute.return_value = _scalar_result(customer)

        result = await repo.get_by_slug("acme", session=session)

        assert result is customer

    @pytest.mark.asyncio
    async def test_get_all_active(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        customers = [MagicMock(spec=CustomerRecord)]
        session.execute.return_value = _scalars_result(customers)

        result = await repo.get_all_active(session=session)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_all_paginated(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        customers = [MagicMock(spec=CustomerRecord)]
        session.execute.side_effect = _count_then_list(3, customers)

        records, total = await repo.get_all_paginated(limit=10, offset=0, session=session)

        assert total == 3
        assert len(records) == 1

    @pytest.mark.asyncio
    async def test_insert(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        record = MagicMock(spec=CustomerRecord)

        await repo.insert(record, session=session)

        session.add.assert_called_once_with(record)
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_found(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        record = MagicMock(spec=CustomerRecord)
        session.execute.return_value = _scalar_result(record)

        from app.modules.platform.interfaces.customer import UpdateCustomerRequest

        result = await repo.update("cust-1", UpdateCustomerRequest(name="New"), session=session)

        assert result is record
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_not_found(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        session.execute.return_value = _scalar_result(None)

        from app.modules.platform.interfaces.customer import UpdateCustomerRequest

        result = await repo.update("missing", UpdateCustomerRequest(name="X"), session=session)

        assert result is None


# ========================== UserRepository ==========================

class TestUserRepository:
    def _make_repo(self) -> UserRepository:
        return UserRepository(session_factory=_mock_session_factory())

    @pytest.mark.asyncio
    async def test_get_by_id(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        user = MagicMock(spec=UserRecord)
        session.execute.return_value = _scalar_result(user)

        result = await repo.get_by_id("u-1", session=session)

        assert result is user

    @pytest.mark.asyncio
    async def test_get_by_email(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        user = MagicMock(spec=UserRecord)
        session.execute.return_value = _scalar_result(user)

        result = await repo.get_by_email("alice@example.com", session=session)

        assert result is user

    @pytest.mark.asyncio
    async def test_insert(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        record = MagicMock(spec=UserRecord)

        await repo.insert(record, session=session)

        session.add.assert_called_once_with(record)
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_keycloak_sub(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        user = MagicMock(spec=UserRecord)
        session.execute.return_value = _scalar_result(user)

        result = await repo.get_by_keycloak_sub("kc-sub-1", session=session)

        assert result is user

    @pytest.mark.asyncio
    async def test_upsert_from_keycloak_existing_user(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        user = MagicMock(spec=UserRecord)
        user.email = "alice@example.com"
        user.name = "Alice"
        user.id = "u-1"
        session.execute.return_value = _scalar_result(user)

        result = await repo.upsert_from_keycloak(
            keycloak_sub="kc-sub-1", email="alice@example.com", name="Alice", session=session
        )

        assert result is user
        # No update needed since email and name match
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_upsert_from_keycloak_existing_user_updated(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        user = MagicMock(spec=UserRecord)
        user.email = "old@example.com"
        user.name = "Old Name"
        user.id = "u-1"
        # execute #1: select by keycloak_sub (found); execute #2: update
        session.execute.side_effect = [_scalar_result(user), MagicMock()]

        result = await repo.upsert_from_keycloak(
            keycloak_sub="kc-sub-1", email="new@example.com", name="New Name", session=session
        )

        assert result is user
        assert result.email == "new@example.com"
        assert result.name == "New Name"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_from_keycloak_match_by_email(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        user = MagicMock(spec=UserRecord)
        user.email = "alice@example.com"
        user.name = "Alice"
        user.id = "u-1"
        user.keycloak_sub = None
        # execute #1: select by keycloak_sub (not found)
        # execute #2: select by email (found)
        # execute #3: update statement
        session.execute.side_effect = [_scalar_result(None), _scalar_result(user), MagicMock()]

        result = await repo.upsert_from_keycloak(
            keycloak_sub="kc-sub-1", email="alice@example.com", name="Alice Updated", session=session
        )

        assert result is user
        assert result.keycloak_sub == "kc-sub-1"
        assert result.name == "Alice Updated"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_from_keycloak_new_user(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        # Not found by keycloak_sub, not found by email
        session.execute.side_effect = [_scalar_result(None), _scalar_result(None)]

        result = await repo.upsert_from_keycloak(
            keycloak_sub="kc-sub-1", email="new@example.com", name="New User", session=session
        )

        assert isinstance(result, UserRecord)
        session.add.assert_called_once()
        session.commit.assert_called_once()
        session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_active(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        users = [MagicMock(spec=UserRecord)]
        session.execute.return_value = _scalars_result(users)

        result = await repo.get_all_active(session=session)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_all(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        users = [MagicMock(spec=UserRecord)]
        session.execute.return_value = _scalars_result(users)

        result = await repo.get_all(session=session)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_all_paginated(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        users = [MagicMock(spec=UserRecord)]
        session.execute.side_effect = _count_then_list(10, users)

        records, total = await repo.get_all_paginated(limit=5, offset=0, session=session)

        assert total == 10
        assert len(records) == 1

    @pytest.mark.asyncio
    async def test_update(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        user = MagicMock(spec=UserRecord)
        session.execute.side_effect = [MagicMock(), _scalar_result(user)]

        from app.modules.platform.interfaces.user import UpdateUserRequest

        result = await repo.update("u-1", UpdateUserRequest(name="New"), session=session)

        assert result is user
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_empty_values(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        user = MagicMock(spec=UserRecord)
        session.execute.return_value = _scalar_result(user)

        from app.modules.platform.interfaces.user import UpdateUserRequest

        result = await repo.update("u-1", UpdateUserRequest(), session=session)

        assert result is user


# ========================== OperatorRepository ==========================

class TestOperatorRepository:
    def _make_repo(self) -> OperatorRepository:
        return OperatorRepository(session_factory=_mock_session_factory())

    @pytest.mark.asyncio
    async def test_get_by_id(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        op = MagicMock(spec=OperatorRecord)
        session.execute.return_value = _scalar_result(op)

        result = await repo.get_by_id("op-1", session=session)

        assert result is op

    @pytest.mark.asyncio
    async def test_get_by_email(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        op = MagicMock(spec=OperatorRecord)
        session.execute.return_value = _scalar_result(op)

        result = await repo.get_by_email("ops@example.com", session=session)

        assert result is op

    @pytest.mark.asyncio
    async def test_get_by_keycloak_sub(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        op = MagicMock(spec=OperatorRecord)
        session.execute.return_value = _scalar_result(op)

        result = await repo.get_by_keycloak_sub("kc-op-1", session=session)

        assert result is op

    @pytest.mark.asyncio
    async def test_insert(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        record = MagicMock(spec=OperatorRecord)

        await repo.insert(record, session=session)

        session.add.assert_called_once_with(record)
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_from_keycloak_existing_no_change(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        op = MagicMock(spec=OperatorRecord)
        op.email = "ops@example.com"
        op.name = "Ops"
        op.id = "op-1"
        session.execute.return_value = _scalar_result(op)

        result = await repo.upsert_from_keycloak(
            keycloak_sub="kc-1", email="ops@example.com", name="Ops", session=session
        )

        assert result is op
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_upsert_from_keycloak_existing_updated(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        op = MagicMock(spec=OperatorRecord)
        op.email = "old@example.com"
        op.name = "Old"
        op.id = "op-1"
        # execute #1: select by keycloak_sub (found); execute #2: update
        session.execute.side_effect = [_scalar_result(op), MagicMock()]

        result = await repo.upsert_from_keycloak(
            keycloak_sub="kc-1", email="new@example.com", name="New", session=session
        )

        assert result.email == "new@example.com"
        assert result.name == "New"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_from_keycloak_match_by_email(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        op = MagicMock(spec=OperatorRecord)
        op.email = "ops@example.com"
        op.name = "Ops"
        op.id = "op-1"
        op.keycloak_sub = None
        # execute #1: select by keycloak_sub (not found)
        # execute #2: select by email (found)
        # execute #3: update statement
        session.execute.side_effect = [_scalar_result(None), _scalar_result(op), MagicMock()]

        result = await repo.upsert_from_keycloak(
            keycloak_sub="kc-1", email="ops@example.com", name="Ops Updated", session=session
        )

        assert result.keycloak_sub == "kc-1"
        assert result.name == "Ops Updated"
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_from_keycloak_new_operator(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        session.execute.side_effect = [_scalar_result(None), _scalar_result(None)]

        result = await repo.upsert_from_keycloak(
            keycloak_sub="kc-1", email="new@example.com", name="New Ops", session=session
        )

        assert isinstance(result, OperatorRecord)
        session.add.assert_called_once()
        session.commit.assert_called_once()
        session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_active(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        ops = [MagicMock(spec=OperatorRecord)]
        session.execute.return_value = _scalars_result(ops)

        result = await repo.get_all_active(session=session)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_all(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        ops = [MagicMock(spec=OperatorRecord)]
        session.execute.return_value = _scalars_result(ops)

        result = await repo.get_all(session=session)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_all_paginated(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        ops = [MagicMock(spec=OperatorRecord)]
        session.execute.side_effect = _count_then_list(7, ops)

        records, total = await repo.get_all_paginated(limit=10, offset=0, session=session)

        assert total == 7
        assert len(records) == 1

    @pytest.mark.asyncio
    async def test_update(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        op = MagicMock(spec=OperatorRecord)
        session.execute.side_effect = [MagicMock(), _scalar_result(op)]

        from app.modules.platform.interfaces.operator import UpdateOperatorRequest

        result = await repo.update("op-1", UpdateOperatorRequest(name="Updated"), session=session)

        assert result is op
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_excludes_platform_role(self) -> None:
        """platform_role should be excluded from DB update (handled by FGA)."""
        repo = self._make_repo()
        session = _mock_session()
        op = MagicMock(spec=OperatorRecord)
        # Only the select query (no update because platform_role is excluded and no other field)
        session.execute.return_value = _scalar_result(op)

        from app.modules.platform.interfaces.operator import UpdateOperatorRequest

        result = await repo.update("op-1", UpdateOperatorRequest(platform_role="ops_admin"), session=session)

        assert result is op


# ========================== APIKeyRepository ==========================

class TestAPIKeyRepository:
    def _make_repo(self) -> APIKeyRepository:
        return APIKeyRepository(session_factory=_mock_session_factory())

    @pytest.mark.asyncio
    async def test_get_by_hash_found(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        key = MagicMock()
        key.expires_at = None
        session.execute.return_value = _scalar_result(key)

        result = await repo.get_by_hash("hash123", session=session)

        assert result is key

    @pytest.mark.asyncio
    async def test_get_by_hash_not_found(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        session.execute.return_value = _scalar_result(None)

        result = await repo.get_by_hash("hash123", session=session)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_hash_expired(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        key = MagicMock()
        key.expires_at = datetime(2020, 1, 1, tzinfo=UTC)
        session.execute.return_value = _scalar_result(key)

        result = await repo.get_by_hash("hash123", session=session)

        assert result is None

    @pytest.mark.asyncio
    async def test_insert(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        record = MagicMock()

        await repo.insert(record, session=session)

        session.add.assert_called_once_with(record)
        session.commit.assert_called_once()


# ========================== PortfolioRepository ==========================

class TestPortfolioRepository:
    def _make_repo(self) -> PortfolioRepository:
        return PortfolioRepository(session_factory=_mock_session_factory())

    @pytest.mark.asyncio
    async def test_get_by_fund(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        portfolios = [MagicMock(), MagicMock()]
        session.execute.return_value = _scalars_result(portfolios)

        result = await repo.get_by_fund("fund-1", session=session)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_by_id(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        portfolio = MagicMock()
        session.execute.return_value = _scalar_result(portfolio)

        from uuid import UUID

        result = await repo.get_by_id(UUID("12345678-1234-1234-1234-123456789012"), session=session)

        assert result is portfolio

    @pytest.mark.asyncio
    async def test_insert(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        record = MagicMock()

        await repo.insert(record, session=session)

        session.add.assert_called_once_with(record)
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert_batch(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        records = [MagicMock(), MagicMock()]

        await repo.insert_batch(records, session=session)

        session.add_all.assert_called_once_with(records)
        session.commit.assert_called_once()


# ========================== ServicingEdgeRepository ==========================

class TestServicingEdgeRepository:
    def _make_repo(self) -> ServicingEdgeRepository:
        return ServicingEdgeRepository(session_factory=_mock_session_factory())

    @pytest.mark.asyncio
    async def test_get_active_edge(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        edge = MagicMock()
        session.execute.return_value = _scalar_result(edge)

        result = await repo.get_active_edge("admin-1", "client-1", session=session)

        assert result is edge

    @pytest.mark.asyncio
    async def test_get_by_id(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        edge = MagicMock()
        session.execute.return_value = _scalar_result(edge)

        result = await repo.get_by_id("edge-1", session=session)

        assert result is edge

    @pytest.mark.asyncio
    async def test_get_client_customers(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        edges = [MagicMock(), MagicMock()]
        session.execute.return_value = _scalars_result(edges)

        result = await repo.get_client_customers("admin-1", session=session)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_admin_customers(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        edges = [MagicMock()]
        session.execute.return_value = _scalars_result(edges)

        result = await repo.get_admin_customers("client-1", session=session)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_insert(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        record = MagicMock()

        await repo.insert(record, session=session)

        session.add.assert_called_once_with(record)
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_scoped_roles(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        edge = MagicMock()
        # First call: update execute, second: get_by_id's select
        session.execute.side_effect = [MagicMock(), _scalar_result(edge)]

        result = await repo.update_scoped_roles("edge-1", ["admin", "viewer"], session=session)

        assert result is edge
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_suspend(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        edge = MagicMock()
        session.execute.side_effect = [MagicMock(), _scalar_result(edge)]

        result = await repo.suspend("edge-1", session=session)

        assert result is edge
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_terminate(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        edge = MagicMock()
        session.execute.side_effect = [MagicMock(), _scalar_result(edge)]

        result = await repo.terminate("edge-1", session=session)

        assert result is edge
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_reactivate(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        edge = MagicMock()
        session.execute.side_effect = [MagicMock(), _scalar_result(edge)]

        result = await repo.reactivate("edge-1", session=session)

        assert result is edge
        session.commit.assert_called_once()


# ========================== AuditLogRepository ==========================

class TestAuditLogRepository:
    def _make_repo(self) -> AuditLogRepository:
        return AuditLogRepository(session_factory=_mock_session_factory())

    @pytest.mark.asyncio
    async def test_fetch_last_hash_empty(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        session.execute.return_value = _scalar_result(None)

        result = await repo._fetch_last_hash(session)

        assert result == ""

    @pytest.mark.asyncio
    async def test_fetch_last_hash_found(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        session.execute.return_value = _scalar_result("abc123")

        result = await repo._fetch_last_hash(session)

        assert result == "abc123"

    @pytest.mark.asyncio
    async def test_insert_event(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        # First call: _fetch_last_hash; second: insert execute
        session.execute.side_effect = [_scalar_result(""), MagicMock()]

        event = MagicMock()
        event.event_id = "evt-1"
        event.event_type = "order.created"
        event.actor_id = "u-1"
        event.actor_type = "user"
        event.fund_slug = "alpha"
        event.data = {"order_id": "o-1"}
        event.event_version = 1
        event.timestamp = datetime(2024, 1, 1, tzinfo=UTC)

        await repo.insert(event, session=session)

        assert session.execute.call_count == 2
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert_admin_event(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        session.execute.return_value = _scalar_result("")  # _fetch_last_hash

        from app.shared.audit.events import AuditEventType

        await repo.insert_admin_event(
            event_type=AuditEventType.ADMIN_USER_CREATED,
            actor_id="op-1",
            actor_type="operator",
            fund_slug="alpha",
            payload={"name": "test"},
            session=session,
        )

        session.add.assert_called_once()
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert_admin_event_no_payload(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        session.execute.return_value = _scalar_result("")

        from app.shared.audit.events import AuditEventType

        await repo.insert_admin_event(
            event_type=AuditEventType.ADMIN_USER_CREATED,
            actor_id="op-1",
            actor_type="operator",
            session=session,
        )

        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert_cdc_event(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        session.execute.return_value = _scalar_result("")

        await repo.insert_cdc_event(
            event_type="cdc.orders.insert",
            actor_id="system",
            actor_type="system",
            fund_slug="alpha",
            payload={"table": "orders"},
            session=session,
        )

        session.add.assert_called_once()
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert_cdc_event_no_payload(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        session.execute.return_value = _scalar_result("")

        await repo.insert_cdc_event(
            event_type="cdc.orders.insert",
            actor_id="system",
            actor_type="system",
            session=session,
        )

        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_no_filters(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        records = [MagicMock()]
        session.execute.side_effect = _count_then_list(1, records)

        result_records, total = await repo.query(session=session)

        assert total == 1
        assert len(result_records) == 1

    @pytest.mark.asyncio
    async def test_query_with_filters(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        session.execute.side_effect = _count_then_list(0, [])

        records, total = await repo.query(
            fund_slug="alpha",
            event_type="order.created",
            actor_id="u-1",
            entity_type="order",
            entity_id="o-1",
            correlation_id="corr-1",
            limit=50,
            offset=10,
            session=session,
        )

        assert total == 0
        assert records == []

    @pytest.mark.asyncio
    async def test_get_records_for_period(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        record = MagicMock()
        record.event_id = "evt-1"
        record.event_type = "order.created"
        record.actor_id = "u-1"
        record.actor_type = "user"
        record.fund_slug = "alpha"
        record.payload = {"data": "test"}
        record.created_at = datetime(2024, 1, 15, tzinfo=UTC)

        session.execute.return_value = _scalars_result([record])

        result = await repo.get_records_for_period(
            start=datetime(2024, 1, 1, tzinfo=UTC),
            end=datetime(2024, 2, 1, tzinfo=UTC),
            session=session,
        )

        assert len(result) == 1
        assert result[0]["event_id"] == "evt-1"
        assert result[0]["actor_id"] == "u-1"

    @pytest.mark.asyncio
    async def test_get_records_for_period_with_fund_slug(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        session.execute.return_value = _scalars_result([])

        result = await repo.get_records_for_period(
            start=datetime(2024, 1, 1, tzinfo=UTC),
            end=datetime(2024, 2, 1, tzinfo=UTC),
            fund_slug="alpha",
            session=session,
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_count_for_period(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        session.execute.return_value = _scalar_result(42)

        result = await repo.count_for_period(
            start=datetime(2024, 1, 1, tzinfo=UTC),
            end=datetime(2024, 2, 1, tzinfo=UTC),
            session=session,
        )

        assert result == 42

    @pytest.mark.asyncio
    async def test_count_for_period_with_fund_slug(self) -> None:
        repo = self._make_repo()
        session = _mock_session()
        session.execute.return_value = _scalar_result(10)

        result = await repo.count_for_period(
            start=datetime(2024, 1, 1, tzinfo=UTC),
            end=datetime(2024, 2, 1, tzinfo=UTC),
            fund_slug="alpha",
            session=session,
        )

        assert result == 10
