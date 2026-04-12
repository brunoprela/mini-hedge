"""Unit tests for PriceFinalizationService — closing price capture."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.eod.core.price_finalization import PriceFinalizationService

_BIZ_DATE = date(2026, 4, 11)


def _make_instrument(ticker: str) -> MagicMock:
    i = MagicMock()
    i.ticker = ticker
    return i


def _make_price(mid: Decimal) -> MagicMock:
    p = MagicMock()
    p.mid = mid
    return p


def _make_service(
    instruments: list | None = None,
    prices: dict[str, MagicMock | None] | None = None,
) -> tuple[PriceFinalizationService, AsyncMock]:
    price_repo = AsyncMock()
    price_repo.upsert_price = AsyncMock()

    market_data = AsyncMock()

    async def _get_latest(instrument_id: str, **kw) -> MagicMock | None:
        if prices and instrument_id in prices:
            return prices[instrument_id]
        return None

    market_data.get_latest_price = AsyncMock(side_effect=_get_latest)

    sm_service = AsyncMock()
    sm_service.get_all_active = AsyncMock(return_value=instruments or [])

    svc = PriceFinalizationService(
        price_repo=price_repo,
        market_data_service=market_data,
        security_master_service=sm_service,
    )
    return svc, price_repo


class TestPriceFinalization:
    @pytest.mark.asyncio
    async def test_finalizes_all_instruments(self) -> None:
        instruments = [_make_instrument("AAPL"), _make_instrument("MSFT")]
        prices = {
            "AAPL": _make_price(Decimal("248.50")),
            "MSFT": _make_price(Decimal("415.20")),
        }
        svc, price_repo = _make_service(instruments, prices)

        result = await svc.finalize_prices(_BIZ_DATE)

        assert result.business_date == _BIZ_DATE
        assert result.total_instruments == 2
        assert result.finalized_count == 2
        assert result.missing_count == 0
        assert result.is_complete is True
        assert price_repo.upsert_price.call_count == 2

    @pytest.mark.asyncio
    async def test_tracks_missing_prices(self) -> None:
        instruments = [_make_instrument("AAPL"), _make_instrument("MISSING")]
        prices = {"AAPL": _make_price(Decimal("248.50"))}
        svc, price_repo = _make_service(instruments, prices)

        result = await svc.finalize_prices(_BIZ_DATE)

        assert result.finalized_count == 1
        assert result.missing_count == 1
        assert result.missing_instruments == ["MISSING"]
        assert result.is_complete is False
        assert price_repo.upsert_price.call_count == 1

    @pytest.mark.asyncio
    async def test_empty_instrument_universe(self) -> None:
        svc, price_repo = _make_service([], {})

        result = await svc.finalize_prices(_BIZ_DATE)

        assert result.total_instruments == 0
        assert result.finalized_count == 0
        assert result.is_complete is True
        price_repo.upsert_price.assert_not_called()

    @pytest.mark.asyncio
    async def test_null_mid_treated_as_missing(self) -> None:
        instruments = [_make_instrument("AAPL")]
        price_with_null_mid = MagicMock()
        price_with_null_mid.mid = None
        prices = {"AAPL": price_with_null_mid}
        svc, price_repo = _make_service(instruments, prices)

        result = await svc.finalize_prices(_BIZ_DATE)

        assert result.finalized_count == 0
        assert result.missing_count == 1
        assert result.missing_instruments == ["AAPL"]
        price_repo.upsert_price.assert_not_called()

    @pytest.mark.asyncio
    async def test_upsert_called_with_correct_args(self) -> None:
        instruments = [_make_instrument("AAPL")]
        prices = {"AAPL": _make_price(Decimal("248.50"))}
        svc, price_repo = _make_service(instruments, prices)

        await svc.finalize_prices(_BIZ_DATE)

        call_kwargs = price_repo.upsert_price.call_args.kwargs
        assert call_kwargs["instrument_id"] == "AAPL"
        assert call_kwargs["business_date"] == _BIZ_DATE
        assert call_kwargs["close_price"] == Decimal("248.50")
        assert call_kwargs["source"] == "market_data"
        assert call_kwargs["finalized_by"] == "eod_orchestrator"

    @pytest.mark.asyncio
    async def test_all_missing_is_not_complete(self) -> None:
        instruments = [_make_instrument("A"), _make_instrument("B"), _make_instrument("C")]
        svc, _ = _make_service(instruments, {})

        result = await svc.finalize_prices(_BIZ_DATE)

        assert result.total_instruments == 3
        assert result.finalized_count == 0
        assert result.missing_count == 3
        assert result.is_complete is False
