"""Unit tests for per-asset-class exposure normalizers."""

from __future__ import annotations

from decimal import Decimal

from app.modules.exposure.core.normalizers import (
    EquityExposureNormalizer,
    FixedIncomeExposureNormalizer,
    FutureExposureNormalizer,
    OptionExposureNormalizer,
    normalize_exposure,
)
from app.modules.exposure.interfaces import PositionValue

_ONE = Decimal(1)


def _pv(
    mv: Decimal,
    *,
    asset_class: str = "equity",
    quantity: Decimal = Decimal("100"),
    price: Decimal | None = None,
) -> PositionValue:
    return PositionValue(
        instrument_id="TEST",
        quantity=quantity,
        market_price=price or abs(mv / quantity) if quantity else Decimal(0),
        market_value=mv,
        asset_class=asset_class,
    )


class TestOptionExposureNormalizer:
    def test_returns_market_value_times_fx(self) -> None:
        pos = _pv(Decimal("50000"), asset_class="option")
        normalizer = OptionExposureNormalizer()
        result = normalizer.normalize(pos, fx_rate=Decimal("1.25"))
        assert result == Decimal("62500")

    def test_default_fx_rate(self) -> None:
        pos = _pv(Decimal("50000"), asset_class="option")
        normalizer = OptionExposureNormalizer()
        assert normalizer.normalize(pos) == Decimal("50000")


class TestFutureExposureNormalizer:
    def test_returns_market_value_times_fx(self) -> None:
        pos = _pv(Decimal("100000"), asset_class="future")
        normalizer = FutureExposureNormalizer()
        result = normalizer.normalize(pos, fx_rate=Decimal("0.9"))
        assert result == Decimal("90000")


class TestFixedIncomeExposureNormalizer:
    def test_returns_market_value_times_fx(self) -> None:
        pos = _pv(Decimal("200000"), asset_class="fixed_income")
        normalizer = FixedIncomeExposureNormalizer()
        result = normalizer.normalize(pos, fx_rate=Decimal("1.1"))
        assert result == Decimal("220000")


class TestNormalizeExposureDispatch:
    def test_option_dispatches_correctly(self) -> None:
        pos = _pv(Decimal("50000"), asset_class="option")
        result = normalize_exposure(pos)
        assert result == Decimal("50000")

    def test_future_dispatches_correctly(self) -> None:
        pos = _pv(Decimal("100000"), asset_class="future")
        result = normalize_exposure(pos)
        assert result == Decimal("100000")

    def test_fixed_income_dispatches_correctly(self) -> None:
        pos = _pv(Decimal("200000"), asset_class="fixed_income")
        result = normalize_exposure(pos)
        assert result == Decimal("200000")

    def test_unknown_asset_class_uses_equity_fallback(self) -> None:
        pos = _pv(
            Decimal("100000"),
            asset_class="cryptocurrency",
            quantity=Decimal("10"),
            price=Decimal("10000"),
        )
        result = normalize_exposure(pos)
        # Fallback is EquityExposureNormalizer: quantity * price * fx_rate
        assert result == Decimal("100000")
