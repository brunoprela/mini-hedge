"""Unit tests for MarketDataService — price/FX CRUD, in-memory cache, OHLCV."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.market_data.interfaces import FXRateSnapshot, PriceSnapshot
from app.modules.market_data.services.market_data import MarketDataService

_NOW = datetime.now(timezone.utc)


def _make_price_record(
    instrument_id: str = "AAPL",
    bid: Decimal = Decimal("149"),
    ask: Decimal = Decimal("151"),
    mid: Decimal = Decimal("150"),
    volume: int = 1000,
) -> MagicMock:
    r = MagicMock()
    r.instrument_id = instrument_id
    r.bid = bid
    r.ask = ask
    r.mid = mid
    r.volume = volume
    r.timestamp = _NOW
    r.source = "simulator"
    return r


def _make_fx_rate_record(
    base: str = "USD",
    quote: str = "EUR",
    rate: Decimal = Decimal("0.92"),
) -> MagicMock:
    r = MagicMock()
    r.base_currency = base
    r.quote_currency = quote
    r.rate = rate
    r.timestamp = _NOW
    r.source = "manual"
    return r


def _make_snapshot(instrument_id: str = "AAPL") -> PriceSnapshot:
    return PriceSnapshot(
        instrument_id=instrument_id,
        bid=Decimal("149"),
        ask=Decimal("151"),
        mid=Decimal("150"),
        volume=Decimal("1000"),
        timestamp=_NOW,
        source="simulator",
    )


def _make_fx_snapshot(base: str = "USD", quote: str = "EUR") -> FXRateSnapshot:
    return FXRateSnapshot(
        base_currency=base,
        quote_currency=quote,
        rate=Decimal("0.92"),
        timestamp=_NOW,
        source="manual",
    )


def _make_service() -> MarketDataService:
    price_repo = AsyncMock()
    price_repo.get_latest = AsyncMock(return_value=None)
    price_repo.get_history = AsyncMock(return_value=[])
    price_repo.insert = AsyncMock()
    price_repo.get_ohlcv_bars = AsyncMock(return_value=[])

    fx_repo = AsyncMock()
    fx_repo.get_latest = AsyncMock(return_value=None)
    fx_repo.get_latest_all = AsyncMock(return_value=[])
    fx_repo.insert = AsyncMock()

    return MarketDataService(price_repo=price_repo, fx_repo=fx_repo)


class TestGetLatestPrice:
    @pytest.mark.asyncio
    async def test_returns_from_cache(self) -> None:
        svc = _make_service()
        snapshot = _make_snapshot("AAPL")
        svc.update_latest(snapshot)

        result = await svc.get_latest_price("AAPL")

        assert result is not None
        assert result.instrument_id == "AAPL"
        # Should NOT hit the DB
        svc._price_repo.get_latest.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_db(self) -> None:
        svc = _make_service()
        record = _make_price_record("MSFT")
        svc._price_repo.get_latest = AsyncMock(return_value=record)

        result = await svc.get_latest_price("MSFT")

        assert result is not None
        assert result.instrument_id == "MSFT"
        svc._price_repo.get_latest.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_if_not_found(self) -> None:
        svc = _make_service()

        result = await svc.get_latest_price("UNKNOWN")

        assert result is None


class TestPriceHistory:
    @pytest.mark.asyncio
    async def test_returns_history(self) -> None:
        svc = _make_service()
        records = [_make_price_record(), _make_price_record()]
        svc._price_repo.get_history = AsyncMock(return_value=records)

        result = await svc.get_price_history("AAPL", _NOW, _NOW)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_empty_history(self) -> None:
        svc = _make_service()

        result = await svc.get_price_history("AAPL", _NOW, _NOW)

        assert result == []


class TestStorePrice:
    @pytest.mark.asyncio
    async def test_persists_price(self) -> None:
        svc = _make_service()
        snapshot = _make_snapshot()

        await svc.store_price(snapshot)

        svc._price_repo.insert.assert_called_once()


class TestOHLCVBars:
    @pytest.mark.asyncio
    async def test_returns_bars(self) -> None:
        svc = _make_service()
        svc._price_repo.get_ohlcv_bars = AsyncMock(return_value=[
            {
                "open": Decimal("148"),
                "high": Decimal("152"),
                "low": Decimal("147"),
                "close": Decimal("150"),
                "volume": Decimal("5000"),
                "period_start": _NOW,
                "period_end": _NOW,
            },
        ])

        result = await svc.get_ohlcv_bars("AAPL", _NOW, _NOW)

        assert len(result) == 1
        assert result[0].instrument_id == "AAPL"
        assert result[0].close == Decimal("150")

    @pytest.mark.asyncio
    async def test_empty_bars(self) -> None:
        svc = _make_service()

        result = await svc.get_ohlcv_bars("AAPL", _NOW, _NOW)

        assert result == []


class TestFXRates:
    @pytest.mark.asyncio
    async def test_get_fx_rate(self) -> None:
        svc = _make_service()
        record = _make_fx_rate_record()
        svc._fx_repo.get_latest = AsyncMock(return_value=record)

        result = await svc.get_fx_rate("USD", "EUR")

        assert result is not None
        assert result.rate == Decimal("0.92")

    @pytest.mark.asyncio
    async def test_get_fx_rate_not_found(self) -> None:
        svc = _make_service()

        result = await svc.get_fx_rate("USD", "JPY")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_fx_rates(self) -> None:
        svc = _make_service()
        svc._fx_repo.get_latest_all = AsyncMock(
            return_value=[_make_fx_rate_record(), _make_fx_rate_record("EUR", "GBP")]
        )

        result = await svc.get_all_fx_rates()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_store_fx_rate(self) -> None:
        svc = _make_service()
        snapshot = _make_fx_snapshot()

        await svc.store_fx_rate(snapshot)

        svc._fx_repo.insert.assert_called_once()

    def test_update_fx_rate_in_memory(self) -> None:
        svc = _make_service()
        snapshot = _make_fx_snapshot("USD", "GBP")

        svc.update_fx_rate(snapshot)

        assert svc.fx_converter.get_rate("USD", "GBP") is not None

    def test_fx_converter_property(self) -> None:
        svc = _make_service()
        assert svc.fx_converter is not None
