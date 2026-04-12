"""Unit tests for TCARepository — verifies SQL queries and session handling
without touching a real database."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.modules.tca.models.tca_result import TCAResultRecord
from app.modules.tca.repositories.tca import TCARepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session_factory():
    """Build a mock TenantSessionFactory whose __call__ yields a mock session."""
    sf = MagicMock()
    mock_session = AsyncMock()
    session_cm = AsyncMock()
    session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    session_cm.__aexit__ = AsyncMock(return_value=False)
    sf.return_value = session_cm
    return sf, mock_session


# ---------------------------------------------------------------------------
# TCARepository.save
# ---------------------------------------------------------------------------


class TestTCARepositorySave:
    @pytest.mark.asyncio
    async def test_save_adds_and_flushes(self) -> None:
        sf, mock_session = _make_session_factory()
        repo = TCARepository(sf)

        record = MagicMock(spec=TCAResultRecord)
        result = await repo.save(record)

        mock_session.add.assert_called_once_with(record)
        mock_session.flush.assert_awaited_once()
        mock_session.commit.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(record)
        assert result is record

    @pytest.mark.asyncio
    async def test_save_uses_provided_session(self) -> None:
        sf, _ = _make_session_factory()
        repo = TCARepository(sf)

        provided_session = AsyncMock()
        record = MagicMock(spec=TCAResultRecord)
        result = await repo.save(record, session=provided_session)

        provided_session.add.assert_called_once_with(record)
        provided_session.flush.assert_awaited_once()
        assert result is record


# ---------------------------------------------------------------------------
# TCARepository.get_by_order_id
# ---------------------------------------------------------------------------


class TestTCARepositoryGetByOrderId:
    @pytest.mark.asyncio
    async def test_returns_record_when_found(self) -> None:
        sf, mock_session = _make_session_factory()
        repo = TCARepository(sf)

        record = MagicMock(spec=TCAResultRecord)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = record
        mock_session.execute = AsyncMock(return_value=result_mock)

        order_id = uuid4()
        result = await repo.get_by_order_id(order_id)

        assert result is record
        mock_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        sf, mock_session = _make_session_factory()
        repo = TCARepository(sf)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=result_mock)

        result = await repo.get_by_order_id(uuid4())
        assert result is None


# ---------------------------------------------------------------------------
# TCARepository.get_by_order_ids
# ---------------------------------------------------------------------------


class TestTCARepositoryGetByOrderIds:
    @pytest.mark.asyncio
    async def test_returns_empty_for_empty_input(self) -> None:
        sf, mock_session = _make_session_factory()
        repo = TCARepository(sf)

        result = await repo.get_by_order_ids([])

        assert result == []
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_records_for_given_ids(self) -> None:
        sf, mock_session = _make_session_factory()
        repo = TCARepository(sf)

        r1 = MagicMock(spec=TCAResultRecord)
        r2 = MagicMock(spec=TCAResultRecord)
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [r1, r2]
        mock_session.execute = AsyncMock(return_value=result_mock)

        ids = [str(uuid4()), str(uuid4())]
        result = await repo.get_by_order_ids(ids)

        assert result == [r1, r2]
        mock_session.execute.assert_awaited_once()
