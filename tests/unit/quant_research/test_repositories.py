"""Unit tests for quant_research repositories — verifies SQL queries and
session handling without touching a real database."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.quant_research.models.factor_definition import FactorDefinitionRecord
from app.modules.quant_research.models.factor_exposure import FactorExposureRecord
from app.modules.quant_research.models.factor_return import FactorReturnRecord
from app.modules.quant_research.models.regime_snapshot import RegimeSnapshotRecord
from app.modules.quant_research.repositories.factor_definition import FactorDefinitionRepository
from app.modules.quant_research.repositories.factor_exposure import FactorExposureRepository
from app.modules.quant_research.repositories.factor_return import FactorReturnRepository
from app.modules.quant_research.repositories.regime import RegimeRepository


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
# FactorDefinitionRepository
# ---------------------------------------------------------------------------


class TestFactorDefinitionRepository:
    @pytest.mark.asyncio
    async def test_create(self):
        sf, mock_session = _make_session_factory()
        repo = FactorDefinitionRepository(sf)
        record = MagicMock(spec=FactorDefinitionRecord)

        await repo.create(record)

        mock_session.add.assert_called_once_with(record)
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_with_provided_session(self):
        sf, _ = _make_session_factory()
        repo = FactorDefinitionRepository(sf)
        provided_session = AsyncMock()
        record = MagicMock(spec=FactorDefinitionRecord)

        await repo.create(record, session=provided_session)

        provided_session.add.assert_called_once_with(record)
        provided_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_id(self):
        sf, mock_session = _make_session_factory()
        repo = FactorDefinitionRepository(sf)
        record = MagicMock(spec=FactorDefinitionRecord)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = record
        mock_session.execute.return_value = result_mock

        result = await repo.get_by_id("some-uuid")

        assert result is record
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self):
        sf, mock_session = _make_session_factory()
        repo = FactorDefinitionRepository(sf)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result_mock

        result = await repo.get_by_id("missing-uuid")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_name(self):
        sf, mock_session = _make_session_factory()
        repo = FactorDefinitionRepository(sf)
        record = MagicMock(spec=FactorDefinitionRecord)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = record
        mock_session.execute.return_value = result_mock

        result = await repo.get_by_name("momentum")

        assert result is record
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_all_active_only(self):
        sf, mock_session = _make_session_factory()
        repo = FactorDefinitionRepository(sf)

        records = [MagicMock(spec=FactorDefinitionRecord)]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = records
        mock_session.execute.return_value = result_mock

        result = await repo.list_all(active_only=True)

        assert result == records
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_all_include_inactive(self):
        sf, mock_session = _make_session_factory()
        repo = FactorDefinitionRepository(sf)

        records = [MagicMock(spec=FactorDefinitionRecord)]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = records
        mock_session.execute.return_value = result_mock

        result = await repo.list_all(active_only=False)

        assert result == records


# ---------------------------------------------------------------------------
# FactorExposureRepository
# ---------------------------------------------------------------------------


class TestFactorExposureRepository:
    @pytest.mark.asyncio
    async def test_save_many(self):
        sf, mock_session = _make_session_factory()
        repo = FactorExposureRepository(sf)
        r1 = MagicMock(spec=FactorExposureRecord)
        r2 = MagicMock(spec=FactorExposureRecord)

        await repo.save_many([r1, r2])

        assert mock_session.add.call_count == 2
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_many_empty(self):
        sf, mock_session = _make_session_factory()
        repo = FactorExposureRepository(sf)

        await repo.save_many([])

        mock_session.add.assert_not_called()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_factor_date(self):
        sf, mock_session = _make_session_factory()
        repo = FactorExposureRepository(sf)

        records = [MagicMock(spec=FactorExposureRecord)]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = records
        mock_session.execute.return_value = result_mock

        result = await repo.get_by_factor_date("factor-id", date(2024, 1, 15))

        assert result == records
        mock_session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# FactorReturnRepository
# ---------------------------------------------------------------------------


class TestFactorReturnRepository:
    @pytest.mark.asyncio
    async def test_save_many(self):
        sf, mock_session = _make_session_factory()
        repo = FactorReturnRepository(sf)
        r1 = MagicMock(spec=FactorReturnRecord)

        await repo.save_many([r1])

        mock_session.add.assert_called_once_with(r1)
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_factor_no_date_filter(self):
        sf, mock_session = _make_session_factory()
        repo = FactorReturnRepository(sf)

        records = [MagicMock(spec=FactorReturnRecord)]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = records
        mock_session.execute.return_value = result_mock

        result = await repo.get_by_factor("factor-id")

        assert result == records

    @pytest.mark.asyncio
    async def test_get_by_factor_with_start_date(self):
        sf, mock_session = _make_session_factory()
        repo = FactorReturnRepository(sf)

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = result_mock

        result = await repo.get_by_factor("factor-id", start_date=date(2024, 1, 1))

        assert result == []

    @pytest.mark.asyncio
    async def test_get_by_factor_with_end_date(self):
        sf, mock_session = _make_session_factory()
        repo = FactorReturnRepository(sf)

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = result_mock

        result = await repo.get_by_factor("factor-id", end_date=date(2024, 12, 31))

        assert result == []

    @pytest.mark.asyncio
    async def test_get_by_factor_with_both_dates(self):
        sf, mock_session = _make_session_factory()
        repo = FactorReturnRepository(sf)

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = result_mock

        result = await repo.get_by_factor(
            "factor-id",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )

        assert result == []


# ---------------------------------------------------------------------------
# RegimeRepository
# ---------------------------------------------------------------------------


class TestRegimeRepository:
    @pytest.mark.asyncio
    async def test_save_snapshot(self):
        sf, mock_session = _make_session_factory()
        repo = RegimeRepository(sf)
        record = MagicMock(spec=RegimeSnapshotRecord)

        await repo.save_snapshot(record)

        mock_session.add.assert_called_once_with(record)
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_latest(self):
        sf, mock_session = _make_session_factory()
        repo = RegimeRepository(sf)
        record = MagicMock(spec=RegimeSnapshotRecord)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = record
        mock_session.execute.return_value = result_mock

        result = await repo.get_latest()

        assert result is record

    @pytest.mark.asyncio
    async def test_get_latest_none(self):
        sf, mock_session = _make_session_factory()
        repo = RegimeRepository(sf)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result_mock

        result = await repo.get_latest()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_history(self):
        sf, mock_session = _make_session_factory()
        repo = RegimeRepository(sf)

        records = [MagicMock(spec=RegimeSnapshotRecord)]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = records
        mock_session.execute.return_value = result_mock

        result = await repo.get_history(limit=50)

        assert result == records

    @pytest.mark.asyncio
    async def test_get_history_default_limit(self):
        sf, mock_session = _make_session_factory()
        repo = RegimeRepository(sf)

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = result_mock

        result = await repo.get_history()

        assert result == []
