"""Unit tests for insight_engine — covering uncovered rule branches."""

from __future__ import annotations

import pytest

from app.modules.ai_analysis.core.insight_engine import generate_portfolio_insights


class TestEmptyAndZeroPortfolio:
    def test_empty_positions_returns_empty(self):
        assert generate_portfolio_insights([]) == []

    def test_zero_total_value_returns_empty(self):
        positions = [
            {"instrument_id": "X", "market_value": 0, "sector": "Tech"},
        ]
        assert generate_portfolio_insights(positions) == []

    def test_negative_total_value_returns_empty(self):
        positions = [
            {"instrument_id": "X", "market_value": -100, "sector": "Tech"},
        ]
        assert generate_portfolio_insights(positions) == []


class TestSmallPositions:
    def test_small_position_flagged(self):
        positions = [
            {"instrument_id": "AAPL", "market_value": 99_000, "sector": "Tech"},
            {"instrument_id": "TINY", "market_value": 100, "sector": "Tech"},
        ]
        insights = generate_portfolio_insights(positions)
        small = [i for i in insights if i.insight_type == "small_position_cleanup"]
        assert len(small) == 1
        assert "TINY" in small[0].affected_instruments

    def test_no_small_positions(self):
        positions = [
            {"instrument_id": "AAPL", "market_value": 50_000, "sector": "Tech"},
            {"instrument_id": "MSFT", "market_value": 50_000, "sector": "Tech"},
        ]
        insights = generate_portfolio_insights(positions)
        small = [i for i in insights if i.insight_type == "small_position_cleanup"]
        assert len(small) == 0


class TestSectorCorrelation:
    def test_top5_same_sector_flagged_critical(self):
        positions = [
            {"instrument_id": f"STOCK{i}", "market_value": 10_000 * (6 - i), "sector": "Tech"}
            for i in range(5)
        ]
        insights = generate_portfolio_insights(positions)
        corr = [i for i in insights if i.insight_type == "high_correlation"]
        assert len(corr) == 1
        assert corr[0].severity == "critical"
        assert "Tech" in corr[0].title

    def test_fewer_than_5_positions_no_correlation_insight(self):
        positions = [
            {"instrument_id": f"S{i}", "market_value": 25_000, "sector": "Tech"}
            for i in range(4)
        ]
        insights = generate_portfolio_insights(positions)
        corr = [i for i in insights if i.insight_type == "high_correlation"]
        assert len(corr) == 0

    def test_top5_mixed_sectors_no_correlation_insight(self):
        sectors = ["Tech", "Health", "Energy", "Finance", "Consumer"]
        positions = [
            {"instrument_id": f"S{i}", "market_value": 20_000, "sector": sectors[i]}
            for i in range(5)
        ]
        insights = generate_portfolio_insights(positions)
        corr = [i for i in insights if i.insight_type == "high_correlation"]
        assert len(corr) == 0


class TestCashDrag:
    def test_high_cash_flagged(self):
        positions = [
            {"instrument_id": "AAPL", "market_value": 70_000, "sector": "Tech"},
            {"instrument_id": "CASH", "market_value": 30_000, "sector": "Cash", "asset_class": "cash"},
        ]
        insights = generate_portfolio_insights(positions)
        cash = [i for i in insights if i.insight_type == "cash_drag"]
        assert len(cash) == 1
        assert "30.0%" in cash[0].title

    def test_low_cash_not_flagged(self):
        positions = [
            {"instrument_id": "AAPL", "market_value": 95_000, "sector": "Tech"},
            {"instrument_id": "CASH", "market_value": 5_000, "sector": "Cash", "asset_class": "cash"},
        ]
        insights = generate_portfolio_insights(positions)
        cash = [i for i in insights if i.insight_type == "cash_drag"]
        assert len(cash) == 0

    def test_cash_detected_by_asset_class(self):
        positions = [
            {"instrument_id": "AAPL", "market_value": 60_000, "sector": "Tech"},
            {"instrument_id": "MMF", "market_value": 40_000, "sector": "Other", "asset_class": "Cash"},
        ]
        insights = generate_portfolio_insights(positions)
        cash = [i for i in insights if i.insight_type == "cash_drag"]
        assert len(cash) == 1


class TestFactorTilts:
    def test_extreme_tilt_both_directions(self):
        positions = [
            {"instrument_id": "X", "market_value": 1000, "sector": "Tech"},
        ]
        factor_exposures = {"momentum": 2.5, "value": -3.0, "size": 1.0}
        insights = generate_portfolio_insights(positions, factor_exposures=factor_exposures)
        tilts = [i for i in insights if i.insight_type == "factor_tilt"]
        assert len(tilts) == 2
        names = {t.title for t in tilts}
        assert any("momentum" in n for n in names)
        assert any("value" in n for n in names)

    def test_invalid_z_score_skipped(self):
        positions = [
            {"instrument_id": "X", "market_value": 1000, "sector": "Tech"},
        ]
        factor_exposures = {"momentum": "not_a_number", "value": 0.5}
        insights = generate_portfolio_insights(positions, factor_exposures=factor_exposures)
        tilts = [i for i in insights if i.insight_type == "factor_tilt"]
        assert len(tilts) == 0

    def test_none_factor_exposures(self):
        positions = [
            {"instrument_id": "X", "market_value": 1000, "sector": "Tech"},
        ]
        insights = generate_portfolio_insights(positions, factor_exposures=None)
        tilts = [i for i in insights if i.insight_type == "factor_tilt"]
        assert len(tilts) == 0

    def test_short_factor_tilt_description(self):
        positions = [
            {"instrument_id": "X", "market_value": 1000, "sector": "Tech"},
        ]
        factor_exposures = {"beta": -2.5}
        insights = generate_portfolio_insights(positions, factor_exposures=factor_exposures)
        tilts = [i for i in insights if i.insight_type == "factor_tilt"]
        assert len(tilts) == 1
        assert "short" in tilts[0].description
