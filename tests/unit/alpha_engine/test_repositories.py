"""Unit tests for alpha engine repositories."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.alpha_engine.repositories.optimization_run import OptimizationRunRepository
from app.modules.alpha_engine.repositories.optimization_weight import OptimizationWeightRepository
from app.modules.alpha_engine.repositories.order_intent import OrderIntentRepository
from app.modules.alpha_engine.repositories.scenario_run import ScenarioRunRepository


def _mock_session() -> AsyncMock:
    """Create a mock async session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    return session


def _make_repo(repo_cls):
    """Create a repo with a mocked session factory."""
    session = _mock_session()
    factory = MagicMock()

    @asynccontextmanager
    async def _fake_factory():
        yield session

    factory.side_effect = _fake_factory
    repo = repo_cls(session_factory=factory)
    return repo, session


# ---------------------------------------------------------------------------
# OptimizationRunRepository
# ---------------------------------------------------------------------------


class TestOptimizationRunRepository:
    @pytest.mark.asyncio
    async def test_save_adds_and_commits(self) -> None:
        repo, session = _make_repo(OptimizationRunRepository)
        record = MagicMock()

        await repo.save(record)

        session.add.assert_called_once_with(record)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_with_explicit_session(self) -> None:
        repo, _ = _make_repo(OptimizationRunRepository)
        explicit = _mock_session()
        record = MagicMock()

        await repo.save(record, session=explicit)

        explicit.add.assert_called_once_with(record)
        explicit.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_many(self) -> None:
        repo, session = _make_repo(OptimizationRunRepository)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["run1", "run2"]
        session.execute = AsyncMock(return_value=mock_result)

        rows = await repo.get_many(uuid4(), limit=10)

        assert rows == ["run1", "run2"]
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_id_found(self) -> None:
        repo, session = _make_repo(OptimizationRunRepository)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "the-run"
        session.execute = AsyncMock(return_value=mock_result)

        row = await repo.get_by_id("run-123")

        assert row == "the-run"
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self) -> None:
        repo, session = _make_repo(OptimizationRunRepository)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        row = await repo.get_by_id("missing")

        assert row is None


# ---------------------------------------------------------------------------
# OptimizationWeightRepository
# ---------------------------------------------------------------------------


class TestOptimizationWeightRepository:
    @pytest.mark.asyncio
    async def test_save_many(self) -> None:
        repo, session = _make_repo(OptimizationWeightRepository)
        records = [MagicMock(), MagicMock(), MagicMock()]

        await repo.save_many(records)

        assert session.add.call_count == 3
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_many_empty(self) -> None:
        repo, session = _make_repo(OptimizationWeightRepository)

        await repo.save_many([])

        session.add.assert_not_called()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_run(self) -> None:
        repo, session = _make_repo(OptimizationWeightRepository)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["w1", "w2"]
        session.execute = AsyncMock(return_value=mock_result)

        rows = await repo.get_by_run("run-id")

        assert rows == ["w1", "w2"]
        session.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# OrderIntentRepository
# ---------------------------------------------------------------------------


class TestOrderIntentRepository:
    @pytest.mark.asyncio
    async def test_save_many(self) -> None:
        repo, session = _make_repo(OrderIntentRepository)
        records = [MagicMock(), MagicMock()]

        await repo.save_many(records)

        assert session.add.call_count == 2
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_portfolio(self) -> None:
        repo, session = _make_repo(OrderIntentRepository)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["i1"]
        session.execute = AsyncMock(return_value=mock_result)

        rows = await repo.get_by_portfolio(uuid4())

        assert rows == ["i1"]
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_run(self) -> None:
        repo, session = _make_repo(OrderIntentRepository)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["i1", "i2"]
        session.execute = AsyncMock(return_value=mock_result)

        rows = await repo.get_by_run("run-id")

        assert rows == ["i1", "i2"]
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_status(self) -> None:
        repo, session = _make_repo(OrderIntentRepository)
        session.execute = AsyncMock()

        await repo.update_status("intent-1", "approved")

        assert session.execute.await_count == 1
        session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# ScenarioRunRepository
# ---------------------------------------------------------------------------


class TestScenarioRunRepository:
    @pytest.mark.asyncio
    async def test_save_adds_and_commits(self) -> None:
        repo, session = _make_repo(ScenarioRunRepository)
        record = MagicMock()

        await repo.save(record)

        session.add.assert_called_once_with(record)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_many(self) -> None:
        repo, session = _make_repo(ScenarioRunRepository)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["s1", "s2"]
        session.execute = AsyncMock(return_value=mock_result)

        rows = await repo.get_many(uuid4(), limit=5)

        assert rows == ["s1", "s2"]
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_id_found(self) -> None:
        repo, session = _make_repo(ScenarioRunRepository)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "scenario-1"
        session.execute = AsyncMock(return_value=mock_result)

        row = await repo.get_by_id("sc-123")

        assert row == "scenario-1"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self) -> None:
        repo, session = _make_repo(ScenarioRunRepository)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        row = await repo.get_by_id("missing")

        assert row is None


# ---------------------------------------------------------------------------
# Package re-exports
# ---------------------------------------------------------------------------


class TestRepositoryPackageExports:
    def test_all_repos_importable(self) -> None:
        from app.modules.alpha_engine.repositories import (
            OptimizationRunRepository,
            OptimizationWeightRepository,
            OrderIntentRepository,
            ScenarioRunRepository,
        )

        assert OptimizationRunRepository is not None
        assert OptimizationWeightRepository is not None
        assert OrderIntentRepository is not None
        assert ScenarioRunRepository is not None
