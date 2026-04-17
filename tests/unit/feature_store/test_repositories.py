"""Unit tests for feature_store repositories — mocked SQLAlchemy sessions."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.feature_store.models.feature_definition import FeatureDefinitionRecord
from app.modules.feature_store.models.feature_set import FeatureSetRecord
from app.modules.feature_store.models.feature_value import FeatureValueRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_session() -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    return session


def _mock_session_factory(session: AsyncMock | None = None) -> MagicMock:
    sf = MagicMock()
    s = session or _mock_session()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=s)
    cm.__aexit__ = AsyncMock(return_value=False)
    sf.return_value = cm
    return sf


def _make_scalars_result(items: list) -> MagicMock:
    result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = items
    result.scalars.return_value = scalars_mock
    return result


def _make_scalar_one_or_none_result(item: object | None) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = item
    return result


NOW = datetime.now(UTC)


# ---------------------------------------------------------------------------
# FeatureDefinitionRepository
# ---------------------------------------------------------------------------


class TestFeatureDefinitionRepository:
    def _make_repo(self, session: AsyncMock | None = None):
        from app.modules.feature_store.repositories.feature_definition import (
            FeatureDefinitionRepository,
        )

        sf = _mock_session_factory(session)
        return FeatureDefinitionRepository(session_factory=sf), session or sf.return_value.__aenter__.return_value

    async def test_insert(self):
        session = _mock_session()
        repo, s = self._make_repo(session)
        record = MagicMock(spec=FeatureDefinitionRecord)

        await repo.insert(record, session=s)

        s.add.assert_called_once_with(record)
        s.commit.assert_called_once()

    async def test_get_by_id_found(self):
        session = _mock_session()
        repo, s = self._make_repo(session)
        record = MagicMock(spec=FeatureDefinitionRecord)
        s.execute.return_value = _make_scalar_one_or_none_result(record)

        result = await repo.get_by_id("some-id", session=s)

        assert result is record

    async def test_get_by_id_not_found(self):
        session = _mock_session()
        repo, s = self._make_repo(session)
        s.execute.return_value = _make_scalar_one_or_none_result(None)

        result = await repo.get_by_id("missing-id", session=s)

        assert result is None

    async def test_get_by_name(self):
        session = _mock_session()
        repo, s = self._make_repo(session)
        record = MagicMock(spec=FeatureDefinitionRecord)
        s.execute.return_value = _make_scalar_one_or_none_result(record)

        result = await repo.get_by_name("sma_5", session=s)

        assert result is record

    async def test_list_all_no_filters(self):
        session = _mock_session()
        repo, s = self._make_repo(session)
        records = [MagicMock(spec=FeatureDefinitionRecord) for _ in range(3)]
        s.execute.return_value = _make_scalars_result(records)

        result = await repo.list_all(session=s)

        assert len(result) == 3

    async def test_list_all_with_entity_type_and_status(self):
        session = _mock_session()
        repo, s = self._make_repo(session)
        records = [MagicMock(spec=FeatureDefinitionRecord)]
        s.execute.return_value = _make_scalars_result(records)

        result = await repo.list_all(
            entity_type="instrument", status="active", session=s
        )

        assert len(result) == 1

    async def test_list_all_with_tags(self):
        session = _mock_session()
        repo, s = self._make_repo(session)
        records = [MagicMock(spec=FeatureDefinitionRecord)]
        s.execute.return_value = _make_scalars_result(records)

        result = await repo.list_all(tags=["momentum", "risk"], session=s)

        assert len(result) == 1

    async def test_update_with_values(self):
        session = _mock_session()
        repo, s = self._make_repo(session)
        # After update, get_by_id is called — return a record
        updated = MagicMock(spec=FeatureDefinitionRecord)
        s.execute.return_value = _make_scalar_one_or_none_result(updated)

        result = await repo.update(
            "feat-id",
            expression="sma(prices, 10)",
            version=2,
            status="active",
            session=s,
        )

        # execute is called for update + get_by_id
        assert s.execute.call_count == 2
        s.commit.assert_called_once()

    async def test_update_empty_values_skips_execute(self):
        session = _mock_session()
        repo, s = self._make_repo(session)
        updated = MagicMock(spec=FeatureDefinitionRecord)
        s.execute.return_value = _make_scalar_one_or_none_result(updated)

        result = await repo.update("feat-id", session=s)

        # Only get_by_id call, no update execute
        assert s.execute.call_count == 1
        s.commit.assert_not_called()


# ---------------------------------------------------------------------------
# FeatureValueRepository
# ---------------------------------------------------------------------------


class TestFeatureValueRepository:
    def _make_repo(self, session: AsyncMock | None = None):
        from app.modules.feature_store.repositories.feature_value import (
            FeatureValueRepository,
        )

        sf = _mock_session_factory(session)
        return FeatureValueRepository(session_factory=sf), session or sf.return_value.__aenter__.return_value

    async def test_insert_batch(self):
        session = _mock_session()
        repo, s = self._make_repo(session)
        records = [MagicMock(spec=FeatureValueRecord) for _ in range(3)]

        await repo.insert_batch(records, session=s)

        s.add_all.assert_called_once_with(records)
        s.commit.assert_called_once()

    async def test_get_values_latest_only(self):
        session = _mock_session()
        repo, s = self._make_repo(session)
        record = MagicMock(spec=FeatureValueRecord)
        s.execute.return_value = _make_scalars_result([record])

        result = await repo.get_values("feat-id", "AAPL", session=s)

        assert len(result) == 1

    async def test_get_values_all(self):
        session = _mock_session()
        repo, s = self._make_repo(session)
        records = [MagicMock(spec=FeatureValueRecord) for _ in range(5)]
        s.execute.return_value = _make_scalars_result(records)

        result = await repo.get_values("feat-id", "AAPL", latest_only=False, session=s)

        assert len(result) == 5

    async def test_get_feature_vector(self):
        session = _mock_session()
        repo, s = self._make_repo(session)

        rec1 = MagicMock(spec=FeatureValueRecord)
        rec2 = MagicMock(spec=FeatureValueRecord)

        # First call returns rec1, second returns rec2
        s.execute.side_effect = [
            _make_scalar_one_or_none_result(rec1),
            _make_scalar_one_or_none_result(rec2),
        ]

        result = await repo.get_feature_vector(
            "AAPL", ["feat-1", "feat-2"], session=s
        )

        assert result == {"feat-1": rec1, "feat-2": rec2}

    async def test_get_feature_vector_missing_value(self):
        session = _mock_session()
        repo, s = self._make_repo(session)

        s.execute.return_value = _make_scalar_one_or_none_result(None)

        result = await repo.get_feature_vector("AAPL", ["feat-1"], session=s)

        assert result == {}

    async def test_get_stats(self):
        session = _mock_session()
        repo, s = self._make_repo(session)

        mock_row = MagicMock()
        mock_row.count = 50
        mock_row.mean = 25.5
        mock_row.std = 5.0
        mock_row.min_val = 10.0
        mock_row.max_val = 40.0
        mock_row.null_count = 2
        mock_row.last_computed = NOW

        mock_result = MagicMock()
        mock_result.one.return_value = mock_row
        s.execute.return_value = mock_result

        result = await repo.get_stats("feat-id", session=s)

        assert result["count"] == 50
        assert result["mean"] == 25.5
        assert result["null_count"] == 2


# ---------------------------------------------------------------------------
# FeatureSetRepository
# ---------------------------------------------------------------------------


class TestFeatureSetRepository:
    def _make_repo(self, session: AsyncMock | None = None):
        from app.modules.feature_store.repositories.feature_set import (
            FeatureSetRepository,
        )

        sf = _mock_session_factory(session)
        return FeatureSetRepository(session_factory=sf), session or sf.return_value.__aenter__.return_value

    async def test_insert(self):
        session = _mock_session()
        repo, s = self._make_repo(session)
        record = MagicMock(spec=FeatureSetRecord)

        await repo.insert(record, session=s)

        s.add.assert_called_once_with(record)
        s.commit.assert_called_once()

    async def test_get_by_id_found(self):
        session = _mock_session()
        repo, s = self._make_repo(session)
        record = MagicMock(spec=FeatureSetRecord)
        s.execute.return_value = _make_scalar_one_or_none_result(record)

        result = await repo.get_by_id("set-id", session=s)

        assert result is record

    async def test_get_by_id_not_found(self):
        session = _mock_session()
        repo, s = self._make_repo(session)
        s.execute.return_value = _make_scalar_one_or_none_result(None)

        result = await repo.get_by_id("missing", session=s)

        assert result is None

    async def test_list_all(self):
        session = _mock_session()
        repo, s = self._make_repo(session)
        records = [MagicMock(spec=FeatureSetRecord) for _ in range(2)]
        s.execute.return_value = _make_scalars_result(records)

        result = await repo.list_all(session=s)

        assert len(result) == 2
