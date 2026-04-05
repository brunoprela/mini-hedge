"""Tests for reference data — instrument lookup, filtering, universe sync."""

from __future__ import annotations

from mock_exchange.market_data.simulator import DEFAULT_UNIVERSE
from mock_exchange.reference_data.instruments import (
    INSTRUMENT_UNIVERSE,
    get_all_instruments,
    get_instrument,
)


class TestInstrumentUniverse:
    def test_universe_has_42_instruments(self) -> None:
        assert len(INSTRUMENT_UNIVERSE) == 42

    def test_all_tickers_unique(self) -> None:
        tickers = [i.ticker for i in INSTRUMENT_UNIVERSE]
        assert len(tickers) == len(set(tickers))

    def test_all_are_equity(self) -> None:
        assert all(i.asset_class == "equity" for i in INSTRUMENT_UNIVERSE)


class TestGetInstrument:
    def test_known_ticker(self) -> None:
        info = get_instrument("AAPL")
        assert info is not None
        assert info.ticker == "AAPL"
        assert info.name == "Apple Inc."

    def test_unknown_ticker(self) -> None:
        assert get_instrument("FAKE") is None


class TestGetAllInstruments:
    def test_no_filter_returns_all(self) -> None:
        assert len(get_all_instruments()) == 42

    def test_filter_by_country_gb(self) -> None:
        gb = get_all_instruments(country="GB")
        assert len(gb) == 6
        tickers = {i.ticker for i in gb}
        assert "AZN" in tickers
        assert "SHEL" in tickers

    def test_filter_by_sector_technology(self) -> None:
        tech = get_all_instruments(sector="Technology")
        assert len(tech) == 11

    def test_filter_by_asset_class(self) -> None:
        equities = get_all_instruments(asset_class="equity")
        assert len(equities) == 42

    def test_combined_filters(self) -> None:
        us_tech = get_all_instruments(country="US", sector="Technology")
        tickers = {i.ticker for i in us_tech}
        assert tickers == {"AAPL", "MSFT", "GOOGL", "NVDA", "META"}

    def test_no_match_returns_empty(self) -> None:
        assert get_all_instruments(country="ZZ") == []


class TestSimulatorReferenceDataSync:
    """Ensure simulator universe tickers match reference data tickers."""

    def test_tickers_match(self) -> None:
        sim_tickers = {cfg.ticker for cfg in DEFAULT_UNIVERSE}
        ref_tickers = {info.ticker for info in INSTRUMENT_UNIVERSE}
        assert sim_tickers == ref_tickers, (
            f"Simulator-only: {sim_tickers - ref_tickers}, "
            f"RefData-only: {ref_tickers - sim_tickers}"
        )
