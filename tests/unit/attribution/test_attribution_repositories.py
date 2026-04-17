"""Unit tests for attribution repositories."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.attribution.repositories.brinson_fachler import BrinsonFachlerRepository
from app.modules.attribution.repositories.brinson_fachler_sector import (
    BrinsonFachlerSectorRepository,
)
from app.modules.attribution.repositories.cumulative_attribution import (
    CumulativeAttributionRepository,
)
from app.modules.attribution.repositories.risk_based import RiskBasedRepository
from app.modules.attribution.repositories.risk_factor_contribution import (
    RiskFactorContributionRepository,
)


def _mock_session() -> AsyncMock:
    """Create a mock async session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
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
# BrinsonFachlerRepository
# ---------------------------------------------------------------------------


class TestBrinsonFachlerRepository:
    @pytest.mark.asyncio
    async def test_insert_adds_and_commits(self) -> None:
        repo, session = _make_repo(BrinsonFachlerRepository)
        record = MagicMock()

        await repo.insert(record)

        session.add.assert_called_once_with(record)
        session.flush.assert_awaited_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_insert_with_explicit_session(self) -> None:
        repo, _ = _make_repo(BrinsonFachlerRepository)
        explicit = _mock_session()
        record = MagicMock()

        await repo.insert(record, session=explicit)

        explicit.add.assert_called_once_with(record)
        explicit.flush.assert_awaited_once()
        explicit.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_portfolio(self) -> None:
        repo, session = _make_repo(BrinsonFachlerRepository)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["row1", "row2"]
        session.execute = AsyncMock(return_value=mock_result)

        rows = await repo.get_by_portfolio(uuid4(), date(2026, 1, 1), date(2026, 3, 31))

        assert rows == ["row1", "row2"]
        session.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# BrinsonFachlerSectorRepository
# ---------------------------------------------------------------------------


class TestBrinsonFachlerSectorRepository:
    @pytest.mark.asyncio
    async def test_insert_batch(self) -> None:
        repo, session = _make_repo(BrinsonFachlerSectorRepository)
        records = [MagicMock(), MagicMock()]

        await repo.insert_batch(records)

        assert session.add.call_count == 2
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_bf_result(self) -> None:
        repo, session = _make_repo(BrinsonFachlerSectorRepository)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["s1"]
        session.execute = AsyncMock(return_value=mock_result)

        rows = await repo.get_by_bf_result("some-id")

        assert rows == ["s1"]
        session.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# CumulativeAttributionRepository
# ---------------------------------------------------------------------------


class TestCumulativeAttributionRepository:
    @pytest.mark.asyncio
    async def test_insert(self) -> None:
        repo, session = _make_repo(CumulativeAttributionRepository)
        record = MagicMock()

        await repo.insert(record)

        session.add.assert_called_once_with(record)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_latest(self) -> None:
        repo, session = _make_repo(CumulativeAttributionRepository)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "latest"
        session.execute = AsyncMock(return_value=mock_result)

        row = await repo.get_latest(uuid4())

        assert row == "latest"
        session.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# RiskBasedRepository
# ---------------------------------------------------------------------------


class TestRiskBasedRepository:
    @pytest.mark.asyncio
    async def test_insert_adds_and_commits(self) -> None:
        repo, session = _make_repo(RiskBasedRepository)
        record = MagicMock()

        await repo.insert(record)

        session.add.assert_called_once_with(record)
        session.flush.assert_awaited_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_portfolio(self) -> None:
        repo, session = _make_repo(RiskBasedRepository)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["r1"]
        session.execute = AsyncMock(return_value=mock_result)

        rows = await repo.get_by_portfolio(uuid4(), date(2026, 1, 1), date(2026, 3, 31))

        assert rows == ["r1"]


# ---------------------------------------------------------------------------
# RiskFactorContributionRepository
# ---------------------------------------------------------------------------


class TestRiskFactorContributionRepository:
    @pytest.mark.asyncio
    async def test_insert_batch(self) -> None:
        repo, session = _make_repo(RiskFactorContributionRepository)
        records = [MagicMock(), MagicMock(), MagicMock()]

        await repo.insert_batch(records)

        assert session.add.call_count == 3
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_rb_result(self) -> None:
        repo, session = _make_repo(RiskFactorContributionRepository)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["fc1", "fc2"]
        session.execute = AsyncMock(return_value=mock_result)

        rows = await repo.get_by_rb_result("rb-id")

        assert rows == ["fc1", "fc2"]


# ---------------------------------------------------------------------------
# Repositories __init__ re-exports
# ---------------------------------------------------------------------------


class TestRepositoryPackageExports:
    def test_all_repos_importable(self) -> None:
        from app.modules.attribution.repositories import (
            BrinsonFachlerRepository,
            BrinsonFachlerSectorRepository,
            CumulativeAttributionRepository,
            RiskBasedRepository,
            RiskFactorContributionRepository,
        )

        assert BrinsonFachlerRepository is not None
        assert BrinsonFachlerSectorRepository is not None
        assert CumulativeAttributionRepository is not None
        assert RiskBasedRepository is not None
        assert RiskFactorContributionRepository is not None
