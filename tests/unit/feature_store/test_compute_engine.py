"""Unit tests for FeatureComputeEngine — built-in functions and expression evaluation."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.feature_store.core.compute_engine import (
    BUILTIN_FUNCTIONS,
    FeatureComputeEngine,
    _bbands_width,
    _book_to_market,
    _ema,
    _log_market_cap,
    _pe_ratio,
    _returns,
    _rsi,
    _sma,
    _volatility,
)
from app.modules.feature_store.interfaces import ComputeMethod, FeatureDefinition, FeatureStatus, FeatureType


def _make_definition(
    expression: str,
    compute_method: ComputeMethod = ComputeMethod.PYTHON,
    name: str = "test_feature",
) -> FeatureDefinition:
    return FeatureDefinition(
        id=uuid4(),
        name=name,
        description="test",
        feature_type=FeatureType.NUMERIC,
        compute_method=compute_method,
        expression=expression,
        entity_type="instrument",
        version=1,
        status=FeatureStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


class TestSMA:
    def test_basic(self) -> None:
        assert _sma([10.0, 20.0, 30.0], 3) == 20.0

    def test_window_smaller_than_data(self) -> None:
        assert _sma([10.0, 20.0, 30.0, 40.0], 2) == 35.0

    def test_empty_prices(self) -> None:
        assert _sma([], 5) == 0.0

    def test_zero_window(self) -> None:
        assert _sma([10.0, 20.0], 0) == 0.0


class TestEMA:
    def test_basic(self) -> None:
        result = _ema([10.0, 20.0, 30.0], 3)
        assert result > 0.0

    def test_single_price(self) -> None:
        assert _ema([42.0], 5) == 42.0

    def test_empty_prices(self) -> None:
        assert _ema([], 5) == 0.0

    def test_zero_window(self) -> None:
        assert _ema([10.0], 0) == 0.0


class TestRSI:
    def test_all_gains(self) -> None:
        assert _rsi([10.0, 20.0, 30.0, 40.0], 3) == 100.0

    def test_all_losses(self) -> None:
        result = _rsi([40.0, 30.0, 20.0, 10.0], 3)
        assert result < 50.0

    def test_insufficient_data(self) -> None:
        assert _rsi([10.0], 5) == 50.0

    def test_zero_window(self) -> None:
        assert _rsi([10.0, 20.0], 0) == 50.0


class TestBBandsWidth:
    def test_basic(self) -> None:
        prices = [100.0, 102.0, 98.0, 101.0, 99.0]
        result = _bbands_width(prices, 5)
        assert result > 0.0

    def test_insufficient_data(self) -> None:
        assert _bbands_width([10.0, 20.0], 5) == 0.0

    def test_zero_window(self) -> None:
        assert _bbands_width([10.0], 0) == 0.0

    def test_zero_mean(self) -> None:
        assert _bbands_width([0.0, 0.0, 0.0], 3) == 0.0


class TestReturns:
    def test_positive_return(self) -> None:
        assert _returns([100.0, 110.0], 1) == pytest.approx(0.1)

    def test_negative_return(self) -> None:
        assert _returns([100.0, 90.0], 1) == pytest.approx(-0.1)

    def test_insufficient_data(self) -> None:
        assert _returns([100.0], 1) == 0.0

    def test_zero_old_price(self) -> None:
        assert _returns([0.0, 100.0], 1) == 0.0

    def test_multi_day(self) -> None:
        prices = [100.0, 105.0, 110.0, 120.0]
        result = _returns(prices, 3)
        assert result == pytest.approx(0.2)


class TestVolatility:
    def test_basic(self) -> None:
        prices = [100.0, 102.0, 98.0, 103.0, 97.0, 105.0]
        vol = _volatility(prices, 5)
        assert vol > 0.0

    def test_constant_prices(self) -> None:
        vol = _volatility([100.0, 100.0, 100.0, 100.0], 3)
        assert vol == 0.0

    def test_insufficient_data(self) -> None:
        assert _volatility([100.0], 5) == 0.0

    def test_zero_window(self) -> None:
        assert _volatility([100.0, 110.0], 0) == 0.0

    def test_zero_price_skipped(self) -> None:
        # A zero price in the middle should be skipped in return calc
        prices = [100.0, 0.0, 110.0]
        vol = _volatility(prices, 2)
        assert isinstance(vol, float)


class TestLogMarketCap:
    def test_positive(self) -> None:
        result = _log_market_cap(1_000_000.0)
        assert result > 0.0

    def test_zero(self) -> None:
        assert _log_market_cap(0.0) == 0.0

    def test_negative(self) -> None:
        assert _log_market_cap(-100.0) == 0.0


class TestPERatio:
    def test_basic(self) -> None:
        assert _pe_ratio(150.0, 10.0) == 15.0

    def test_zero_earnings(self) -> None:
        assert _pe_ratio(150.0, 0.0) == 0.0


class TestBookToMarket:
    def test_basic(self) -> None:
        assert _book_to_market(40.0, 100.0) == 0.4

    def test_zero_market_cap(self) -> None:
        assert _book_to_market(40.0, 0.0) == 0.0


class TestFeatureComputeEngine:
    def test_compute_python_sma(self) -> None:
        engine = FeatureComputeEngine()
        defn = _make_definition("sma(prices, 3)")
        data = {"prices": [10.0, 20.0, 30.0]}
        result = engine.compute(defn, data)
        assert result == Decimal("20.0")

    def test_compute_python_rsi(self) -> None:
        engine = FeatureComputeEngine()
        defn = _make_definition("rsi(prices, 3)")
        data = {"prices": [10.0, 20.0, 30.0, 40.0]}
        result = engine.compute(defn, data)
        assert result == Decimal("100.0")

    def test_compute_unknown_function(self) -> None:
        engine = FeatureComputeEngine()
        defn = _make_definition("nonexistent(prices, 3)")
        result = engine.compute(defn, {"prices": [1.0]})
        assert result is None

    def test_compute_malformed_expression(self) -> None:
        engine = FeatureComputeEngine()
        defn = _make_definition("sma")
        result = engine.compute(defn, {"prices": [1.0]})
        assert result is None

    def test_compute_literal_args(self) -> None:
        engine = FeatureComputeEngine()
        defn = _make_definition("pe_ratio(price, earnings)")
        result = engine.compute(defn, {"price": 150.0, "earnings": 10.0})
        assert result == Decimal("15.0")

    def test_compute_decimal_input_conversion(self) -> None:
        engine = FeatureComputeEngine()
        defn = _make_definition("sma(prices, 2)")
        data = {"prices": [Decimal("10"), Decimal("20"), Decimal("30")]}
        result = engine.compute(defn, data)
        assert result == Decimal("25.0")

    def test_compute_decimal_scalar_conversion(self) -> None:
        engine = FeatureComputeEngine()
        defn = _make_definition("pe_ratio(price, earnings)")
        data = {"price": Decimal("150"), "earnings": Decimal("10")}
        result = engine.compute(defn, data)
        assert result == Decimal("15.0")

    def test_compute_derived_uses_python(self) -> None:
        engine = FeatureComputeEngine()
        defn = _make_definition("sma(prices, 2)", compute_method=ComputeMethod.DERIVED)
        data = {"prices": [10.0, 20.0]}
        result = engine.compute(defn, data)
        assert result is not None

    def test_compute_batch(self) -> None:
        engine = FeatureComputeEngine()
        defns = [
            _make_definition("sma(prices, 2)", name="sma_2"),
            _make_definition("returns(prices, 1)", name="ret_1"),
        ]
        entities = {
            "AAPL": {"prices": [100.0, 110.0, 120.0]},
            "MSFT": {"prices": [50.0, 55.0, 60.0]},
        }
        results = engine.compute_batch(defns, entities)
        assert "AAPL" in results
        assert "MSFT" in results
        assert "sma_2" in results["AAPL"]
        assert "ret_1" in results["AAPL"]

    def test_compute_function_error_returns_none(self) -> None:
        engine = FeatureComputeEngine()
        # Pass wrong types to trigger an error inside the function
        defn = _make_definition("sma(prices, window)")
        result = engine.compute(defn, {"prices": "not_a_list", "window": "abc"})
        assert result is None

    def test_unresolved_arg_passed_as_string(self) -> None:
        engine = FeatureComputeEngine()
        defn = _make_definition("pe_ratio(price, unknown_arg)")
        # unknown_arg can't be resolved as int or float
        result = engine.compute(defn, {"price": 150.0})
        assert result is None  # pe_ratio will fail with string arg

    def test_builtin_functions_registered(self) -> None:
        expected = {"sma", "ema", "rsi", "bbands_width", "returns", "volatility", "log_market_cap", "pe_ratio", "book_to_market"}
        assert set(BUILTIN_FUNCTIONS.keys()) == expected
