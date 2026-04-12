"""Unit tests for market data seed module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from app.modules.market_data.seed import _FX_RATES, _PRICES, seed_dev_data


def _make_app(service: MagicMock | None = None) -> MagicMock:
    app = MagicMock()
    if service is not None:
        app.state.market_data_service = service
    else:
        # Simulate missing attribute
        app.state = MagicMock(spec=[])
    return app


def _make_market_data_service() -> MagicMock:
    svc = MagicMock()
    svc.update_fx_rate = MagicMock()
    svc.store_fx_rate = AsyncMock()
    svc.update_latest = MagicMock()
    svc.store_price = AsyncMock()
    svc._latest = {}
    return svc


class TestSeedDevData:
    @pytest.mark.asyncio
    async def test_skips_when_service_not_available(self) -> None:
        """If market_data_service is not on app.state, returns early."""
        app = _make_app(service=None)
        sf = MagicMock()

        await seed_dev_data(app, sf)
        # No crash, no calls

    @pytest.mark.asyncio
    async def test_seeds_fx_rates_and_prices(self) -> None:
        """Seeds all FX rates and instrument prices."""
        svc = _make_market_data_service()
        app = _make_app(service=svc)
        sf = MagicMock()

        await seed_dev_data(app, sf)

        # FX rates: update_fx_rate called for each pair, store_fx_rate too
        assert svc.update_fx_rate.call_count == len(_FX_RATES)
        assert svc.store_fx_rate.call_count == len(_FX_RATES)

        # Prices: update_latest and store_price called for each instrument
        assert svc.update_latest.call_count == len(_PRICES)
        assert svc.store_price.call_count == len(_PRICES)

    @pytest.mark.asyncio
    async def test_skips_cached_prices(self) -> None:
        """Prices already in _latest cache are not re-seeded."""
        svc = _make_market_data_service()
        # Pre-populate cache with AAPL
        svc._latest["AAPL"] = MagicMock()
        app = _make_app(service=svc)
        sf = MagicMock()

        await seed_dev_data(app, sf)

        # Prices should be seeded for all except AAPL
        assert svc.update_latest.call_count == len(_PRICES) - 1

    @pytest.mark.asyncio
    async def test_fx_store_failure_does_not_crash(self) -> None:
        """If store_fx_rate raises, seed continues."""
        svc = _make_market_data_service()
        svc.store_fx_rate = AsyncMock(side_effect=RuntimeError("db duplicate"))
        app = _make_app(service=svc)
        sf = MagicMock()

        await seed_dev_data(app, sf)

        # update_fx_rate still called for all
        assert svc.update_fx_rate.call_count == len(_FX_RATES)

    @pytest.mark.asyncio
    async def test_price_store_failure_does_not_crash(self) -> None:
        """If store_price raises, seed continues."""
        svc = _make_market_data_service()
        svc.store_price = AsyncMock(side_effect=RuntimeError("db duplicate"))
        app = _make_app(service=svc)
        sf = MagicMock()

        await seed_dev_data(app, sf)

        # update_latest still called for all
        assert svc.update_latest.call_count == len(_PRICES)

    @pytest.mark.asyncio
    async def test_no_log_when_data_already_exists(self) -> None:
        """When store fails for all, fx_seeded and price_seeded are 0 — takes else branch."""
        svc = _make_market_data_service()
        svc.store_fx_rate = AsyncMock(side_effect=RuntimeError("dup"))
        svc.store_price = AsyncMock(side_effect=RuntimeError("dup"))
        app = _make_app(service=svc)
        sf = MagicMock()

        # Should not crash, and should take the "data already exists" branch
        await seed_dev_data(app, sf)


class TestSeedConstants:
    def test_fx_rates_not_empty(self) -> None:
        assert len(_FX_RATES) > 0

    def test_prices_not_empty(self) -> None:
        assert len(_PRICES) > 0

    def test_fx_rates_are_tuples_of_three(self) -> None:
        for entry in _FX_RATES:
            assert len(entry) == 3

    def test_prices_are_tuples_of_five(self) -> None:
        for entry in _PRICES:
            assert len(entry) == 5
