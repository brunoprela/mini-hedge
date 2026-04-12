"""Unit tests for corporate actions repository — verifies SQL queries and
session handling without touching a real database."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.corporate_actions.models import ProcessedCorporateActionRecord
from app.modules.corporate_actions.repositories.corporate_actions import (
    CorporateActionsRepository,
)


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
# CorporateActionsRepository
# ---------------------------------------------------------------------------


class TestGetByActionId:
    @pytest.mark.asyncio
    async def test_returns_record_when_found(self):
        sf, mock_session = _make_session_factory()
        repo = CorporateActionsRepository(sf)

        record = MagicMock(spec=ProcessedCorporateActionRecord)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = record
        mock_session.execute.return_value = result_mock

        result = await repo.get_by_action_id("CA-001")

        assert result is record
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        sf, mock_session = _make_session_factory()
        repo = CorporateActionsRepository(sf)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result_mock

        result = await repo.get_by_action_id("MISSING")

        assert result is None

    @pytest.mark.asyncio
    async def test_uses_provided_session(self):
        sf, _ = _make_session_factory()
        repo = CorporateActionsRepository(sf)

        explicit_session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        explicit_session.execute.return_value = result_mock

        await repo.get_by_action_id("CA-001", session=explicit_session)

        explicit_session.execute.assert_called_once()


class TestSave:
    @pytest.mark.asyncio
    async def test_saves_and_returns_record(self):
        sf, mock_session = _make_session_factory()
        repo = CorporateActionsRepository(sf)

        record = MagicMock(spec=ProcessedCorporateActionRecord)
        mock_session.refresh = AsyncMock()

        result = await repo.save(record)

        assert result is record
        mock_session.add.assert_called_once_with(record)
        mock_session.flush.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once_with(record)


class TestGetPending:
    @pytest.mark.asyncio
    async def test_returns_pending_records(self):
        sf, mock_session = _make_session_factory()
        repo = CorporateActionsRepository(sf)

        record = MagicMock(spec=ProcessedCorporateActionRecord)
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [record]
        mock_session.execute.return_value = result_mock

        result = await repo.get_pending()

        assert result == [record]

    @pytest.mark.asyncio
    async def test_filters_by_instrument_id(self):
        sf, mock_session = _make_session_factory()
        repo = CorporateActionsRepository(sf)

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = result_mock

        result = await repo.get_pending(instrument_id="AAPL")

        assert result == []
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_empty_when_none_pending(self):
        sf, mock_session = _make_session_factory()
        repo = CorporateActionsRepository(sf)

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = result_mock

        result = await repo.get_pending()

        assert result == []


class TestListAll:
    @pytest.mark.asyncio
    async def test_returns_all_records(self):
        sf, mock_session = _make_session_factory()
        repo = CorporateActionsRepository(sf)

        r1 = MagicMock(spec=ProcessedCorporateActionRecord)
        r2 = MagicMock(spec=ProcessedCorporateActionRecord)
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [r1, r2]
        mock_session.execute.return_value = result_mock

        result = await repo.list_all()

        assert result == [r1, r2]

    @pytest.mark.asyncio
    async def test_returns_empty_list(self):
        sf, mock_session = _make_session_factory()
        repo = CorporateActionsRepository(sf)

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = result_mock

        result = await repo.list_all()

        assert result == []
