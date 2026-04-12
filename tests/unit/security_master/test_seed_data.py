"""Unit tests for security master seed data — verify record counts and types."""

from __future__ import annotations

from app.modules.security_master.seed import (
    SEED_FIXED_INCOME,
    SEED_FUTURES,
    SEED_FX,
    SEED_INSTRUMENTS,
    SEED_OPTIONS,
    SEED_SWAPS,
    build_all_seed_records,
    build_seed_records,
)
from app.shared.types import AssetClass


class TestEquitySeedData:
    def test_equity_instruments(self) -> None:
        instruments, extensions = build_seed_records()
        assert len(instruments) == len(SEED_INSTRUMENTS)
        assert len(extensions) == len(SEED_INSTRUMENTS)  # all equities have shares_outstanding

    def test_all_equities_have_required_fields(self) -> None:
        for data in SEED_INSTRUMENTS:
            assert "ticker" in data
            assert "currency" in data
            assert data["asset_class"] == AssetClass.EQUITY


class TestNonEquitySeedData:
    def test_fixed_income_count(self) -> None:
        assert len(SEED_FIXED_INCOME) == 3

    def test_options_count(self) -> None:
        assert len(SEED_OPTIONS) == 2

    def test_futures_count(self) -> None:
        assert len(SEED_FUTURES) == 2

    def test_fx_count(self) -> None:
        assert len(SEED_FX) == 3

    def test_swaps_count(self) -> None:
        assert len(SEED_SWAPS) == 2

    def test_asset_classes_correct(self) -> None:
        for data in SEED_FIXED_INCOME:
            assert data["asset_class"] == AssetClass.FIXED_INCOME
        for data in SEED_OPTIONS:
            assert data["asset_class"] == AssetClass.OPTION
        for data in SEED_FUTURES:
            assert data["asset_class"] == AssetClass.FUTURE
        for data in SEED_FX:
            assert data["asset_class"] == AssetClass.FX
        for data in SEED_SWAPS:
            assert data["asset_class"] == AssetClass.SWAP


class TestBuildAllSeedRecords:
    def test_total_instrument_count(self) -> None:
        records = build_all_seed_records()
        equity_count = len(SEED_INSTRUMENTS)
        expected = equity_count + 3 + 2 + 2 + 3 + 2  # FI + options + futures + FX + swaps
        assert len(records["instruments"]) == expected

    def test_all_extension_types_populated(self) -> None:
        records = build_all_seed_records()
        assert len(records["equity_extensions"]) == len(SEED_INSTRUMENTS)
        assert len(records["fixed_income_extensions"]) == 3
        assert len(records["option_extensions"]) == 2
        assert len(records["future_extensions"]) == 2
        assert len(records["fx_extensions"]) == 3
        assert len(records["swap_extensions"]) == 2

    def test_extension_instrument_ids_match(self) -> None:
        records = build_all_seed_records()
        instrument_ids = {r.id for r in records["instruments"]}
        for ext_key in [
            "equity_extensions", "fixed_income_extensions", "option_extensions",
            "future_extensions", "fx_extensions", "swap_extensions",
        ]:
            for ext in records[ext_key]:
                assert ext.instrument_id in instrument_ids, (
                    f"{ext_key} has orphan instrument_id {ext.instrument_id}"
                )
