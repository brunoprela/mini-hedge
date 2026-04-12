"""Unit tests for algo execution strategies — TWAP, VWAP, Iceberg slicing."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.modules.orders.core.algo_strategies import (
    IcebergStrategy,
    TWAPStrategy,
    VWAPStrategy,
    get_strategy,
)

ZERO = Decimal(0)


def _make_params(
    duration_seconds: int = 3600,
    num_slices: int = 4,
    visible_quantity: Decimal | None = None,
    volume_profile: list[Decimal] | None = None,
) -> MagicMock:
    p = MagicMock()
    p.duration_seconds = duration_seconds
    p.num_slices = num_slices
    p.visible_quantity = visible_quantity
    p.volume_profile = volume_profile
    return p


class TestTWAPStrategy:
    def test_even_split(self) -> None:
        strategy = TWAPStrategy()
        params = _make_params(duration_seconds=3600, num_slices=4)

        slices = strategy.compute_slices(Decimal("1000"), params)

        assert len(slices) == 4
        total_qty = sum(s.quantity for s in slices)
        assert total_qty == Decimal("1000")

    def test_timing_equally_spaced(self) -> None:
        strategy = TWAPStrategy()
        params = _make_params(duration_seconds=1200, num_slices=3)

        slices = strategy.compute_slices(Decimal("300"), params)

        assert slices[0].delay_seconds == 0
        assert slices[1].delay_seconds == 400
        assert slices[2].delay_seconds == 800

    def test_remainder_goes_to_last_slice(self) -> None:
        strategy = TWAPStrategy()
        params = _make_params(num_slices=3)

        slices = strategy.compute_slices(Decimal("100"), params)

        # First two should be equal, last gets remainder
        assert slices[0].quantity == slices[1].quantity
        total = sum(s.quantity for s in slices)
        assert total == Decimal("100")

    def test_single_slice(self) -> None:
        strategy = TWAPStrategy()
        params = _make_params(num_slices=1)

        slices = strategy.compute_slices(Decimal("500"), params)

        assert len(slices) == 1
        assert slices[0].quantity == Decimal("500")
        assert slices[0].delay_seconds == 0


class TestVWAPStrategy:
    def test_proportional_to_volume_profile(self) -> None:
        strategy = VWAPStrategy()
        profile = [Decimal("1"), Decimal("3"), Decimal("1")]  # 20%, 60%, 20%
        params = _make_params(duration_seconds=3000, volume_profile=profile)

        slices = strategy.compute_slices(Decimal("1000"), params)

        assert len(slices) == 3
        total = sum(s.quantity for s in slices)
        assert total == Decimal("1000")
        # Middle slice should be largest
        assert slices[1].quantity > slices[0].quantity

    def test_falls_back_to_twap_without_profile(self) -> None:
        strategy = VWAPStrategy()
        params = _make_params(num_slices=2, volume_profile=None)

        slices = strategy.compute_slices(Decimal("100"), params)

        assert len(slices) == 2
        total = sum(s.quantity for s in slices)
        assert total == Decimal("100")

    def test_falls_back_to_twap_with_empty_profile(self) -> None:
        strategy = VWAPStrategy()
        params = _make_params(num_slices=2, volume_profile=[])

        slices = strategy.compute_slices(Decimal("100"), params)

        assert len(slices) == 2

    def test_zero_weight_profile_falls_back(self) -> None:
        strategy = VWAPStrategy()
        params = _make_params(volume_profile=[Decimal("0"), Decimal("0")])

        slices = strategy.compute_slices(Decimal("100"), params)

        # Falls back to TWAP since total weight is zero
        assert len(slices) >= 1
        total = sum(s.quantity for s in slices)
        assert total == Decimal("100")


class TestIcebergStrategy:
    def test_creates_visible_sized_slices(self) -> None:
        strategy = IcebergStrategy()
        params = _make_params(visible_quantity=Decimal("100"))

        slices = strategy.compute_slices(Decimal("500"), params)

        assert len(slices) == 5
        assert all(s.quantity == Decimal("100") for s in slices)
        assert all(s.delay_seconds == 0 for s in slices)  # fill-triggered

    def test_last_slice_is_remainder(self) -> None:
        strategy = IcebergStrategy()
        params = _make_params(visible_quantity=Decimal("300"))

        slices = strategy.compute_slices(Decimal("500"), params)

        assert len(slices) == 2
        assert slices[0].quantity == Decimal("300")
        assert slices[1].quantity == Decimal("200")

    def test_default_visible_is_tenth(self) -> None:
        strategy = IcebergStrategy()
        params = _make_params(visible_quantity=None)

        slices = strategy.compute_slices(Decimal("1000"), params)

        assert len(slices) == 10
        total = sum(s.quantity for s in slices)
        assert total == Decimal("1000")

    def test_total_quantity_preserved(self) -> None:
        strategy = IcebergStrategy()
        params = _make_params(visible_quantity=Decimal("7"))

        slices = strategy.compute_slices(Decimal("20"), params)

        total = sum(s.quantity for s in slices)
        assert total == Decimal("20")


class TestGetStrategy:
    def test_known_strategies(self) -> None:
        for name in ("twap", "vwap", "iceberg"):
            strategy = get_strategy(name)
            assert strategy is not None

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown algo type"):
            get_strategy("moon_phase")
