"""Unit tests for ExposureService — get_current, get_history, take_snapshot."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.modules.exposure.services.exposure import ExposureService

_PORT_ID = uuid4()
_FUND_SLUG = "alpha"


def _make_position(
    instrument_id: str,
    quantity: Decimal,
    market_value: Decimal,
    *,
    currency: str = "USD",
    market_price: Decimal | None = None,
) -> MagicMock:
    p = MagicMock()
    p.instrument_id = instrument_id
    p.quantity = quantity
    p.market_value = market_value
    p.market_price = market_price or abs(market_value / quantity) if quantity else Decimal(0)
    p.currency = currency
    return p


def _make_instrument(
    ticker: str,
    *,
    asset_class: str = "equity",
    sector: str = "Technology",
    country: str = "US",
) -> MagicMock:
    i = MagicMock()
    i.ticker = ticker
    i.asset_class = asset_class
    i.sector = sector
    i.country = country
    return i


def _make_service(
    positions: list | None = None,
    instruments: list | None = None,
) -> tuple[ExposureService, AsyncMock, AsyncMock, AsyncMock]:
    exposure_repo = AsyncMock()
    exposure_repo.save_snapshot = AsyncMock()
    exposure_repo.get_history = AsyncMock(return_value=[])

    position_service = AsyncMock()
    position_service.get_by_portfolio = AsyncMock(return_value=positions or [])

    sm_service = AsyncMock()
    sm_service.get_all_active = AsyncMock(return_value=instruments or [])

    event_bus = AsyncMock()

    svc = ExposureService(
        exposure_repo=exposure_repo,
        position_service=position_service,
        security_master_service=sm_service,
        event_bus=event_bus,
        base_currency="USD",
    )
    return svc, exposure_repo, position_service, event_bus


class TestGetCurrent:
    @pytest.mark.asyncio
    async def test_calculates_exposure_from_positions(self) -> None:
        positions = [
            _make_position("AAPL", Decimal("100"), Decimal("500000")),
            _make_position("MSFT", Decimal("200"), Decimal("300000")),
        ]
        instruments = [
            _make_instrument("AAPL", sector="Technology", country="US"),
            _make_instrument("MSFT", sector="Technology", country="US"),
        ]
        svc, _, _, _ = _make_service(positions, instruments)

        result = await svc.get_current(_PORT_ID)

        assert result.gross_exposure == Decimal("800000")
        assert result.net_exposure == Decimal("800000")
        assert result.long_count == 2
        assert result.short_count == 0

    @pytest.mark.asyncio
    async def test_skips_zero_quantity_positions(self) -> None:
        positions = [
            _make_position("AAPL", Decimal("100"), Decimal("500000")),
            _make_position("MSFT", Decimal("0"), Decimal("0")),
        ]
        instruments = [
            _make_instrument("AAPL"),
            _make_instrument("MSFT"),
        ]
        svc, _, _, _ = _make_service(positions, instruments)

        result = await svc.get_current(_PORT_ID)

        assert result.gross_exposure == Decimal("500000")
        assert result.long_count == 1

    @pytest.mark.asyncio
    async def test_handles_short_positions(self) -> None:
        positions = [
            _make_position("AAPL", Decimal("100"), Decimal("600000")),
            _make_position("TSLA", Decimal("-50"), Decimal("-200000")),
        ]
        instruments = [
            _make_instrument("AAPL"),
            _make_instrument("TSLA"),
        ]
        svc, _, _, _ = _make_service(positions, instruments)

        result = await svc.get_current(_PORT_ID)

        assert result.gross_exposure == Decimal("800000")
        assert result.net_exposure == Decimal("400000")
        assert result.long_count == 1
        assert result.short_count == 1

    @pytest.mark.asyncio
    async def test_empty_portfolio(self) -> None:
        svc, _, _, _ = _make_service([], [])

        result = await svc.get_current(_PORT_ID)

        assert result.gross_exposure == Decimal("0")
        assert result.long_count == 0
        assert result.short_count == 0

    @pytest.mark.asyncio
    async def test_unknown_instrument_uses_none_metadata(self) -> None:
        """Position for an instrument not in security master still computes exposure."""
        positions = [
            _make_position("UNKNOWN", Decimal("100"), Decimal("100000")),
        ]
        svc, _, _, _ = _make_service(positions, [])

        result = await svc.get_current(_PORT_ID)

        assert result.gross_exposure == Decimal("100000")
        assert result.long_count == 1

    @pytest.mark.asyncio
    async def test_fx_conversion_applied(self) -> None:
        """If FX converter is present, non-base-currency values are converted.

        The service converts market_value to base currency, but the equity
        normalizer computes exposure as quantity * market_price (which stays
        in the original currency). The converted market_value appears in the
        breakdowns via _breakdown_by_dimension which reads market_value directly.
        """
        positions = [
            _make_position("VOD.L", Decimal("100"), Decimal("300000"), currency="GBP"),
        ]
        instruments = [
            _make_instrument("VOD.L", country="GB"),
        ]
        fx_converter = MagicMock()
        fx_converter.convert.return_value = Decimal("375000")  # GBP→USD

        svc = ExposureService(
            exposure_repo=AsyncMock(),
            position_service=AsyncMock(return_value=positions),
            security_master_service=AsyncMock(return_value=instruments),
            event_bus=None,
            fx_converter=fx_converter,
            base_currency="USD",
        )
        svc._position_service.get_by_portfolio = AsyncMock(return_value=positions)
        svc._security_master_service.get_all_active = AsyncMock(return_value=instruments)

        result = await svc.get_current(_PORT_ID)

        # FX converter was called for the GBP position
        fx_converter.convert.assert_called_once_with(
            Decimal("300000"), "GBP", "USD"
        )
        # The breakdowns use the FX-converted market_value
        country_bd = {bd.key: bd for bd in result.breakdowns.get("country", [])}
        assert country_bd["GB"].gross_value == Decimal("375000")


class TestGetHistory:
    @pytest.mark.asyncio
    async def test_returns_empty_history(self) -> None:
        svc, exposure_repo, _, _ = _make_service()
        exposure_repo.get_history.return_value = []

        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 3, 31, tzinfo=timezone.utc)
        result = await svc.get_history(_PORT_ID, start, end, fund_slug=_FUND_SLUG)

        assert result == []
        exposure_repo.get_history.assert_called_once()

    @pytest.mark.asyncio
    async def test_maps_records_to_snapshots(self) -> None:
        svc, exposure_repo, _, _ = _make_service()

        record = MagicMock()
        record.id = str(uuid4())
        record.portfolio_id = str(_PORT_ID)
        record.gross_exposure = Decimal("1000000")
        record.net_exposure = Decimal("800000")
        record.long_exposure = Decimal("900000")
        record.short_exposure = Decimal("-100000")
        record.long_count = 5
        record.short_count = 1
        record.snapshot_at = datetime(2026, 3, 15, tzinfo=timezone.utc)
        exposure_repo.get_history.return_value = [record]

        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 3, 31, tzinfo=timezone.utc)
        result = await svc.get_history(_PORT_ID, start, end, fund_slug=_FUND_SLUG)

        assert len(result) == 1
        assert result[0].gross_exposure == Decimal("1000000")
        assert result[0].net_exposure == Decimal("800000")
        assert result[0].fund_slug == _FUND_SLUG


class TestTakeSnapshot:
    @pytest.mark.asyncio
    async def test_persists_snapshot(self) -> None:
        positions = [
            _make_position("AAPL", Decimal("100"), Decimal("500000")),
        ]
        instruments = [_make_instrument("AAPL")]
        svc, exposure_repo, _, _ = _make_service(positions, instruments)

        await svc.take_snapshot(_PORT_ID, fund_slug=_FUND_SLUG)

        exposure_repo.save_snapshot.assert_called_once()
        saved = exposure_repo.save_snapshot.call_args[0][0]
        assert saved.gross_exposure == Decimal("500000")
        assert saved.portfolio_id == str(_PORT_ID)

    @pytest.mark.asyncio
    async def test_publishes_event(self) -> None:
        positions = [
            _make_position("AAPL", Decimal("100"), Decimal("500000")),
        ]
        instruments = [_make_instrument("AAPL")]
        svc, _, _, event_bus = _make_service(positions, instruments)

        await svc.take_snapshot(_PORT_ID, fund_slug=_FUND_SLUG)

        event_bus.publish.assert_called_once()
        topic = event_bus.publish.call_args[0][0]
        assert "exposures.updated" in topic

    @pytest.mark.asyncio
    async def test_no_event_without_fund_slug(self) -> None:
        positions = [
            _make_position("AAPL", Decimal("100"), Decimal("500000")),
        ]
        instruments = [_make_instrument("AAPL")]
        svc, _, _, event_bus = _make_service(positions, instruments)

        await svc.take_snapshot(_PORT_ID, fund_slug=None)

        event_bus.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_event_without_event_bus(self) -> None:
        positions = [
            _make_position("AAPL", Decimal("100"), Decimal("500000")),
        ]
        instruments = [_make_instrument("AAPL")]
        svc, exposure_repo, _, _ = _make_service(positions, instruments)
        svc._event_bus = None

        await svc.take_snapshot(_PORT_ID, fund_slug=_FUND_SLUG)

        exposure_repo.save_snapshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_snapshot_includes_breakdowns(self) -> None:
        positions = [
            _make_position("AAPL", Decimal("100"), Decimal("500000")),
            _make_position("JNJ", Decimal("50"), Decimal("300000")),
        ]
        instruments = [
            _make_instrument("AAPL", sector="Technology"),
            _make_instrument("JNJ", sector="Healthcare"),
        ]
        svc, exposure_repo, _, _ = _make_service(positions, instruments)

        await svc.take_snapshot(_PORT_ID, fund_slug=_FUND_SLUG)

        saved = exposure_repo.save_snapshot.call_args[0][0]
        assert saved.breakdowns is not None
        assert "sector" in saved.breakdowns
