"""Unit tests for PriceValidator — spread, staleness, positivity, bid/ask order."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.modules.market_data.core.price_validator import PriceValidator


@pytest.fixture
def validator() -> PriceValidator:
    return PriceValidator(
        max_spread_bps=Decimal("100"),  # 1% max spread
        max_staleness=timedelta(minutes=10),
    )


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 4, 12, 14, 0, 0, tzinfo=UTC)


class TestPositivity:
    def test_positive_prices_pass(self, validator: PriceValidator, now: datetime) -> None:
        report = validator.validate(
            instrument_id="AAPL", bid=Decimal("149.50"), ask=Decimal("150.50"),
            mid=Decimal("150.00"), timestamp=now, now=now,
        )
        assert report.valid

    def test_negative_bid_fails(self, validator: PriceValidator, now: datetime) -> None:
        report = validator.validate(
            instrument_id="BAD", bid=Decimal("-1.00"), ask=Decimal("1.00"),
            mid=Decimal("0.50"), timestamp=now, now=now,
        )
        assert not report.valid
        failures = [r.check for r in report.failures]
        assert "positivity" in failures

    def test_zero_mid_fails_by_default(self, validator: PriceValidator, now: datetime) -> None:
        report = validator.validate(
            instrument_id="ZERO", bid=Decimal("0"), ask=Decimal("0"),
            mid=Decimal("0"), timestamp=now, now=now,
        )
        assert not report.valid

    def test_zero_mid_allowed_when_configured(self, now: datetime) -> None:
        v = PriceValidator(allow_zero_price=True)
        report = v.validate(
            instrument_id="ZERO", bid=Decimal("0"), ask=Decimal("0"),
            mid=Decimal("0"), timestamp=now, now=now,
        )
        positivity_results = [r for r in report.results if r.check == "positivity"]
        assert all(r.valid for r in positivity_results)


class TestSpread:
    def test_tight_spread_passes(self, validator: PriceValidator, now: datetime) -> None:
        # 10 bps spread on $100 mid
        report = validator.validate(
            instrument_id="TIGHT", bid=Decimal("99.95"), ask=Decimal("100.05"),
            mid=Decimal("100.00"), timestamp=now, now=now,
        )
        spread_result = [r for r in report.results if r.check == "spread"][0]
        assert spread_result.valid

    def test_wide_spread_fails(self, validator: PriceValidator, now: datetime) -> None:
        # 500 bps spread on $100 mid — exceeds 100 bps limit
        report = validator.validate(
            instrument_id="WIDE", bid=Decimal("97.50"), ask=Decimal("102.50"),
            mid=Decimal("100.00"), timestamp=now, now=now,
        )
        spread_result = [r for r in report.results if r.check == "spread"][0]
        assert not spread_result.valid


class TestStaleness:
    def test_fresh_price_passes(self, validator: PriceValidator, now: datetime) -> None:
        report = validator.validate(
            instrument_id="FRESH", bid=Decimal("99.95"), ask=Decimal("100.05"),
            mid=Decimal("100.00"), timestamp=now - timedelta(seconds=30), now=now,
        )
        staleness_result = [r for r in report.results if r.check == "staleness"][0]
        assert staleness_result.valid

    def test_stale_price_fails(self, validator: PriceValidator, now: datetime) -> None:
        report = validator.validate(
            instrument_id="OLD", bid=Decimal("99.95"), ask=Decimal("100.05"),
            mid=Decimal("100.00"), timestamp=now - timedelta(minutes=20), now=now,
        )
        staleness_result = [r for r in report.results if r.check == "staleness"][0]
        assert not staleness_result.valid


class TestBidAskOrder:
    def test_normal_order_passes(self, validator: PriceValidator, now: datetime) -> None:
        report = validator.validate(
            instrument_id="OK", bid=Decimal("99.50"), ask=Decimal("100.50"),
            mid=Decimal("100.00"), timestamp=now, now=now,
        )
        order_result = [r for r in report.results if r.check == "bid_ask_order"][0]
        assert order_result.valid

    def test_crossed_market_fails(self, validator: PriceValidator, now: datetime) -> None:
        report = validator.validate(
            instrument_id="CROSS", bid=Decimal("101.00"), ask=Decimal("99.00"),
            mid=Decimal("100.00"), timestamp=now, now=now,
        )
        order_result = [r for r in report.results if r.check == "bid_ask_order"][0]
        assert not order_result.valid

    def test_equal_bid_ask_passes(self, validator: PriceValidator, now: datetime) -> None:
        report = validator.validate(
            instrument_id="LOCKED", bid=Decimal("100.00"), ask=Decimal("100.00"),
            mid=Decimal("100.00"), timestamp=now, now=now,
        )
        order_result = [r for r in report.results if r.check == "bid_ask_order"][0]
        assert order_result.valid


class TestReportAggregation:
    def test_all_pass_means_valid(self, validator: PriceValidator, now: datetime) -> None:
        report = validator.validate(
            instrument_id="GOOD", bid=Decimal("99.95"), ask=Decimal("100.05"),
            mid=Decimal("100.00"), timestamp=now, now=now,
        )
        assert report.valid
        assert len(report.failures) == 0
        assert len(report.results) == 4

    def test_one_failure_means_invalid(self, validator: PriceValidator, now: datetime) -> None:
        # Crossed market but otherwise fine
        report = validator.validate(
            instrument_id="PARTIAL", bid=Decimal("100.50"), ask=Decimal("99.50"),
            mid=Decimal("100.00"), timestamp=now, now=now,
        )
        assert not report.valid
        assert len(report.failures) >= 1
