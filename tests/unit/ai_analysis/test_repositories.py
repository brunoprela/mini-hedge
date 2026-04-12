"""Unit tests for ai_analysis repositories — mocked sessions, no real DB."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.ai_analysis.repositories.analysis_result import AnalysisResultRepository
from app.modules.ai_analysis.repositories.research_note import ResearchNoteRepository


def _mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    return session


def _make_repo(repo_cls):
    session = _mock_session()
    factory = MagicMock()

    @asynccontextmanager
    async def _fake_factory():
        yield session

    factory.side_effect = _fake_factory
    repo = repo_cls(session_factory=factory)
    return repo, session


# ---------------------------------------------------------------------------
# AnalysisResultRepository
# ---------------------------------------------------------------------------


class TestAnalysisResultRepository:
    @pytest.mark.asyncio
    async def test_save_result_adds_and_commits(self):
        repo, session = _make_repo(AnalysisResultRepository)
        record = MagicMock()

        await repo.save_result(record)

        session.add.assert_called_once_with(record)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_result_with_explicit_session(self):
        repo, _ = _make_repo(AnalysisResultRepository)
        explicit = _mock_session()
        record = MagicMock()

        await repo.save_result(record, session=explicit)

        explicit.add.assert_called_once_with(record)
        explicit.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_result_returns_scalar(self):
        repo, session = _make_repo(AnalysisResultRepository)
        fake_record = MagicMock()
        result_proxy = MagicMock()
        result_proxy.scalar_one_or_none.return_value = fake_record
        session.execute.return_value = result_proxy

        result = await repo.get_result("some-id")

        assert result is fake_record
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_result_returns_none_when_missing(self):
        repo, session = _make_repo(AnalysisResultRepository)
        result_proxy = MagicMock()
        result_proxy.scalar_one_or_none.return_value = None
        session.execute.return_value = result_proxy

        result = await repo.get_result("nonexistent-id")

        assert result is None

    @pytest.mark.asyncio
    async def test_list_results_without_type_filter(self):
        repo, session = _make_repo(AnalysisResultRepository)
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [MagicMock(), MagicMock()]
        result_proxy = MagicMock()
        result_proxy.scalars.return_value = scalars_mock
        session.execute.return_value = result_proxy

        results = await repo.list_results()

        assert len(results) == 2
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_results_with_type_filter(self):
        repo, session = _make_repo(AnalysisResultRepository)
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        result_proxy = MagicMock()
        result_proxy.scalars.return_value = scalars_mock
        session.execute.return_value = result_proxy

        results = await repo.list_results(analysis_type="risk_assessment", limit=10)

        assert results == []
        session.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# ResearchNoteRepository
# ---------------------------------------------------------------------------


class TestResearchNoteRepository:
    @pytest.mark.asyncio
    async def test_save_note_adds_and_commits(self):
        repo, session = _make_repo(ResearchNoteRepository)
        record = MagicMock()

        await repo.save_note(record)

        session.add.assert_called_once_with(record)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_note_with_explicit_session(self):
        repo, _ = _make_repo(ResearchNoteRepository)
        explicit = _mock_session()
        record = MagicMock()

        await repo.save_note(record, session=explicit)

        explicit.add.assert_called_once_with(record)
        explicit.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_notes_without_tags(self):
        repo, session = _make_repo(ResearchNoteRepository)
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [MagicMock()]
        result_proxy = MagicMock()
        result_proxy.scalars.return_value = scalars_mock
        session.execute.return_value = result_proxy

        notes = await repo.list_notes()

        assert len(notes) == 1

    @pytest.mark.asyncio
    async def test_list_notes_with_tags(self):
        repo, session = _make_repo(ResearchNoteRepository)
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        result_proxy = MagicMock()
        result_proxy.scalars.return_value = scalars_mock
        session.execute.return_value = result_proxy

        notes = await repo.list_notes(tags=["macro", "fed"], limit=10)

        assert notes == []
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_note_returns_scalar(self):
        repo, session = _make_repo(ResearchNoteRepository)
        fake_note = MagicMock()
        result_proxy = MagicMock()
        result_proxy.scalar_one_or_none.return_value = fake_note
        session.execute.return_value = result_proxy

        note = await repo.get_note("note-id")

        assert note is fake_note

    @pytest.mark.asyncio
    async def test_get_note_returns_none_when_missing(self):
        repo, session = _make_repo(ResearchNoteRepository)
        result_proxy = MagicMock()
        result_proxy.scalar_one_or_none.return_value = None
        session.execute.return_value = result_proxy

        note = await repo.get_note("missing-id")

        assert note is None

    @pytest.mark.asyncio
    async def test_delete_note(self):
        repo, session = _make_repo(ResearchNoteRepository)

        await repo.delete_note("note-id")

        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()
