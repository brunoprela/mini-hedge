"""Unit tests for compliance repositories — mocked SQLAlchemy sessions."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.compliance.interfaces import UpdateRuleRequest
from app.modules.compliance.models.compliance_rule import ComplianceRuleRecord
from app.modules.compliance.models.compliance_violation import ComplianceViolationRecord
from app.modules.compliance.models.restricted_instrument import RestrictedInstrumentRecord
from app.modules.compliance.models.trade_decision import TradeDecisionRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_session() -> AsyncMock:
    """Create a mock async session that works with execute/scalars patterns."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


def _mock_session_factory(session: AsyncMock | None = None) -> MagicMock:
    """Create a mock TenantSessionFactory."""
    sf = MagicMock()
    s = session or _mock_session()

    # The _session() context manager can receive an explicit session or create one
    # We simulate BaseRepository._session by yielding the mock session
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=s)
    cm.__aexit__ = AsyncMock(return_value=False)
    sf.return_value = cm
    return sf


def _make_scalars_result(items: list) -> MagicMock:
    """Build mock for result.scalars().all()."""
    result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = items
    result.scalars.return_value = scalars_mock
    return result


def _make_scalar_one_or_none_result(item: object | None) -> MagicMock:
    """Build mock for result.scalar_one_or_none()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = item
    return result


def _make_rowcount_result(count: int) -> MagicMock:
    result = MagicMock()
    result.rowcount = count
    return result


# ---------------------------------------------------------------------------
# RuleRepository tests
# ---------------------------------------------------------------------------


class TestRuleRepository:
    def _make_repo(self, session: AsyncMock | None = None):
        from app.modules.compliance.repositories.rule import RuleRepository

        sf = _mock_session_factory(session)
        return RuleRepository(session_factory=sf), session or sf.return_value.__aenter__.return_value

    @pytest.mark.asyncio
    async def test_list_all(self) -> None:
        session = _mock_session()
        records = [MagicMock(spec=ComplianceRuleRecord), MagicMock(spec=ComplianceRuleRecord)]
        session.execute.return_value = _make_scalars_result(records)
        repo, _ = self._make_repo(session)

        result = await repo.list_all()

        assert result == records
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_active(self) -> None:
        session = _mock_session()
        records = [MagicMock(spec=ComplianceRuleRecord)]
        session.execute.return_value = _make_scalars_result(records)
        repo, _ = self._make_repo(session)

        result = await repo.list_active()

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_by_id_found(self) -> None:
        session = _mock_session()
        record = MagicMock(spec=ComplianceRuleRecord)
        session.execute.return_value = _make_scalar_one_or_none_result(record)
        repo, _ = self._make_repo(session)

        result = await repo.get_by_id(uuid4())

        assert result is record

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self) -> None:
        session = _mock_session()
        session.execute.return_value = _make_scalar_one_or_none_result(None)
        repo, _ = self._make_repo(session)

        result = await repo.get_by_id(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_insert(self) -> None:
        session = _mock_session()
        repo, _ = self._make_repo(session)
        record = MagicMock(spec=ComplianceRuleRecord)

        result = await repo.insert(record)

        session.add.assert_called_once_with(record)
        session.flush.assert_called_once()
        session.commit.assert_called_once()
        session.refresh.assert_called_once_with(record)
        assert result is record

    @pytest.mark.asyncio
    async def test_update_with_rule_type_and_severity(self) -> None:
        session = _mock_session()
        repo, _ = self._make_repo(session)
        rule_id = uuid4()

        # Mock get_by_id to return the updated record
        updated = MagicMock(spec=ComplianceRuleRecord)
        repo.get_by_id = AsyncMock(return_value=updated)

        updates = UpdateRuleRequest(
            name="new_name",
            rule_type="concentration_limit",
            severity="warning",
        )
        result = await repo.update(rule_id, updates)

        session.execute.assert_called_once()
        session.commit.assert_called_once()
        assert result is updated

    @pytest.mark.asyncio
    async def test_update_returns_none_when_not_found(self) -> None:
        session = _mock_session()
        repo, _ = self._make_repo(session)

        repo.get_by_id = AsyncMock(return_value=None)

        updates = UpdateRuleRequest(name="x")
        result = await repo.update(uuid4(), updates)

        assert result is None

    @pytest.mark.asyncio
    async def test_deactivate(self) -> None:
        session = _mock_session()
        repo, _ = self._make_repo(session)

        repo.update = AsyncMock(return_value=None)

        rule_id = uuid4()
        await repo.deactivate(rule_id)

        repo.update.assert_called_once()
        call_args = repo.update.call_args
        assert call_args[0][0] == rule_id
        assert call_args[0][1].is_active is False


# ---------------------------------------------------------------------------
# ViolationRepository tests
# ---------------------------------------------------------------------------


class TestViolationRepository:
    def _make_repo(self, session: AsyncMock | None = None):
        from app.modules.compliance.repositories.violation import ViolationRepository

        sf = _mock_session_factory(session)
        return ViolationRepository(session_factory=sf), session or sf.return_value.__aenter__.return_value

    @pytest.mark.asyncio
    async def test_list_active_by_portfolio(self) -> None:
        session = _mock_session()
        records = [MagicMock(spec=ComplianceViolationRecord)]
        session.execute.return_value = _make_scalars_result(records)
        repo, _ = self._make_repo(session)

        result = await repo.list_active_by_portfolio(uuid4())

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_by_id(self) -> None:
        session = _mock_session()
        record = MagicMock(spec=ComplianceViolationRecord)
        session.execute.return_value = _make_scalar_one_or_none_result(record)
        repo, _ = self._make_repo(session)

        result = await repo.get_by_id(uuid4())

        assert result is record

    @pytest.mark.asyncio
    async def test_insert(self) -> None:
        session = _mock_session()
        repo, _ = self._make_repo(session)
        record = MagicMock(spec=ComplianceViolationRecord)

        result = await repo.insert(record)

        session.add.assert_called_once_with(record)
        session.flush.assert_called_once()
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve(self) -> None:
        session = _mock_session()
        repo, _ = self._make_repo(session)
        vid = uuid4()

        resolved_record = MagicMock(spec=ComplianceViolationRecord)
        repo.get_by_id = AsyncMock(return_value=resolved_record)

        result = await repo.resolve(vid, "user-1", resolution_type="manual")

        session.execute.assert_called_once()
        session.commit.assert_called_once()
        assert result is resolved_record


# ---------------------------------------------------------------------------
# RestrictedInstrumentRepository tests
# ---------------------------------------------------------------------------


class TestRestrictedInstrumentRepository:
    def _make_repo(self, session: AsyncMock | None = None):
        from app.modules.compliance.repositories.restricted_instrument import (
            RestrictedInstrumentRepository,
        )

        sf = _mock_session_factory(session)
        return RestrictedInstrumentRepository(session_factory=sf), session or sf.return_value.__aenter__.return_value

    @pytest.mark.asyncio
    async def test_get_by_fund(self) -> None:
        session = _mock_session()
        records = [MagicMock(spec=RestrictedInstrumentRecord)]
        session.execute.return_value = _make_scalars_result(records)
        repo, _ = self._make_repo(session)

        result = await repo.get_by_fund("alpha")

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_instrument_ids(self) -> None:
        session = _mock_session()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = ["AAPL", "TSLA"]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        session.execute.return_value = result_mock
        repo, _ = self._make_repo(session)

        result = await repo.get_instrument_ids("alpha")

        assert result == {"AAPL", "TSLA"}

    @pytest.mark.asyncio
    async def test_insert(self) -> None:
        session = _mock_session()
        repo, _ = self._make_repo(session)

        result = await repo.insert(
            fund_slug="alpha",
            instrument_id="AAPL",
            reason="restricted",
            added_by="user-1",
        )

        session.add.assert_called_once()
        session.flush.assert_called_once()
        assert isinstance(result, RestrictedInstrumentRecord)

    @pytest.mark.asyncio
    async def test_remove_found(self) -> None:
        session = _mock_session()
        session.execute.return_value = _make_rowcount_result(1)
        repo, _ = self._make_repo(session)

        result = await repo.delete(fund_slug="alpha", instrument_id="AAPL")

        assert result is True

    @pytest.mark.asyncio
    async def test_remove_not_found(self) -> None:
        session = _mock_session()
        session.execute.return_value = _make_rowcount_result(0)
        repo, _ = self._make_repo(session)

        result = await repo.delete(fund_slug="alpha", instrument_id="AAPL")

        assert result is False


# ---------------------------------------------------------------------------
# TradeDecisionRepository tests
# ---------------------------------------------------------------------------


class TestTradeDecisionRepository:
    def _make_repo(self, session: AsyncMock | None = None):
        from app.modules.compliance.repositories.trade_decision import TradeDecisionRepository

        sf = _mock_session_factory(session)
        return TradeDecisionRepository(session_factory=sf), session or sf.return_value.__aenter__.return_value

    @pytest.mark.asyncio
    async def test_insert(self) -> None:
        session = _mock_session()
        repo, _ = self._make_repo(session)
        record = MagicMock(spec=TradeDecisionRecord)

        result = await repo.insert(record)

        session.add.assert_called_once_with(record)
        session.flush.assert_called_once()
        session.commit.assert_called_once()
        session.refresh.assert_called_once_with(record)
        assert result is record

    @pytest.mark.asyncio
    async def test_get_by_portfolio(self) -> None:
        session = _mock_session()
        records = [MagicMock(spec=TradeDecisionRecord)]
        session.execute.return_value = _make_scalars_result(records)
        repo, _ = self._make_repo(session)

        result = await repo.get_by_portfolio(uuid4())

        assert len(result) == 1
