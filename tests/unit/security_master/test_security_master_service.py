"""Unit tests for SecurityMasterService — instrument CRUD, search, resolve."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.modules.security_master.interfaces import AssetClass
from app.modules.security_master.services.security_master import SecurityMasterService
from app.shared.errors import NotFoundError


def _make_instrument_record(
    ticker: str = "AAPL",
    asset_class: str = "equity",
    instrument_id: str | None = None,
) -> MagicMock:
    r = MagicMock()
    r.id = instrument_id or str(uuid4())
    r.name = f"{ticker} Inc"
    r.ticker = ticker
    r.asset_class = asset_class
    r.currency = "USD"
    r.exchange = "NASDAQ"
    r.country = "US"
    r.sector = "Technology"
    r.industry = "Software"
    r.annual_drift = 0.1
    r.annual_volatility = 0.25
    r.spread_bps = 3.0
    r.is_active = True
    r.listed_date = date(2020, 1, 1)
    return r


def _make_service(
    instrument: MagicMock | None = None,
    instruments: list | None = None,
    with_identifier_repo: bool = False,
    with_event_bus: bool = False,
) -> SecurityMasterService:
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=instrument)
    repo.get_by_ticker = AsyncMock(return_value=instrument)
    repo.get_all_active = AsyncMock(return_value=instruments or [])
    repo.search = AsyncMock(return_value=instruments or [])
    repo.insert = AsyncMock(side_effect=lambda r, **kw: _assign_id(r))
    repo.update = AsyncMock(return_value=instrument)

    identifier_repo = AsyncMock() if with_identifier_repo else None
    if identifier_repo:
        identifier_repo.resolve = AsyncMock(return_value=instrument)

    event_bus = AsyncMock() if with_event_bus else None

    return SecurityMasterService(
        repository=repo,
        identifier_repo=identifier_repo,
        event_bus=event_bus,
    )


def _assign_id(record):
    if getattr(record, "id", None) is None:
        record.id = str(uuid4())
    if getattr(record, "is_active", None) is None:
        record.is_active = True
    return record


class TestGetByID:
    @pytest.mark.asyncio
    async def test_returns_instrument(self) -> None:
        record = _make_instrument_record()
        svc = _make_service(instrument=record)

        result = await svc.get_by_id(UUID(record.id))

        assert result.ticker == "AAPL"
        assert result.asset_class == AssetClass.EQUITY

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        svc = _make_service(instrument=None)

        with pytest.raises(NotFoundError):
            await svc.get_by_id(uuid4())


class TestGetByTicker:
    @pytest.mark.asyncio
    async def test_returns_instrument(self) -> None:
        record = _make_instrument_record("MSFT")
        svc = _make_service(instrument=record)

        result = await svc.get_by_ticker("MSFT")

        assert result.ticker == "MSFT"

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        svc = _make_service(instrument=None)

        with pytest.raises(NotFoundError):
            await svc.get_by_ticker("UNKNOWN")


class TestGetAllActive:
    @pytest.mark.asyncio
    async def test_returns_list(self) -> None:
        records = [_make_instrument_record("AAPL"), _make_instrument_record("MSFT")]
        svc = _make_service(instruments=records)

        result = await svc.get_all_active()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_filter_by_asset_class(self) -> None:
        svc = _make_service(instruments=[])

        result = await svc.get_all_active(AssetClass.EQUITY)

        svc._instrument_repo.get_all_active.assert_called_once()


class TestSearch:
    @pytest.mark.asyncio
    async def test_returns_results(self) -> None:
        records = [_make_instrument_record("AAPL")]
        svc = _make_service(instruments=records)

        result = await svc.search("AAPL")

        assert len(result) == 1


class TestResolve:
    @pytest.mark.asyncio
    async def test_ticker_resolution(self) -> None:
        record = _make_instrument_record("AAPL")
        svc = _make_service(instrument=record)

        result = await svc.resolve("ticker", "AAPL")

        assert result.ticker == "AAPL"
        svc._instrument_repo.get_by_ticker.assert_called_once()

    @pytest.mark.asyncio
    async def test_isin_resolution(self) -> None:
        record = _make_instrument_record("AAPL")
        svc = _make_service(instrument=record, with_identifier_repo=True)

        result = await svc.resolve("isin", "US0378331005")

        assert result.ticker == "AAPL"

    @pytest.mark.asyncio
    async def test_no_identifier_repo_raises(self) -> None:
        svc = _make_service(instrument=None, with_identifier_repo=False)

        with pytest.raises(NotFoundError):
            await svc.resolve("isin", "US0378331005")

    @pytest.mark.asyncio
    async def test_identifier_not_found(self) -> None:
        svc = _make_service(with_identifier_repo=True)
        svc._identifier_repo.resolve = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError):
            await svc.resolve("cusip", "UNKNOWN")


class TestCreateInstrument:
    @pytest.mark.asyncio
    async def test_creates_and_publishes_event(self) -> None:
        svc = _make_service(with_event_bus=True)

        result = await svc.create_instrument(
            name="Apple Inc",
            ticker="AAPL",
            asset_class=AssetClass.EQUITY,
            currency="USD",
            exchange="NASDAQ",
            country="US",
        )

        assert result.ticker == "AAPL"
        svc._instrument_repo.insert.assert_called_once()
        svc._event_bus.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_without_event_bus(self) -> None:
        svc = _make_service(with_event_bus=False)

        result = await svc.create_instrument(
            name="Microsoft",
            ticker="MSFT",
            asset_class=AssetClass.EQUITY,
            currency="USD",
            exchange="NASDAQ",
            country="US",
        )

        svc._instrument_repo.insert.assert_called_once()


class TestUpdateInstrument:
    @pytest.mark.asyncio
    async def test_updates_instrument(self) -> None:
        record = _make_instrument_record()
        svc = _make_service(instrument=record, with_event_bus=True)

        result = await svc.update_instrument(UUID(record.id), {"sector": "Healthcare"})

        assert result.ticker == "AAPL"
        svc._event_bus.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_not_found(self) -> None:
        svc = _make_service(instrument=None)
        svc._instrument_repo.update = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError):
            await svc.update_instrument(uuid4(), {"sector": "Healthcare"})
