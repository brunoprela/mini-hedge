"""Unit tests for instrument extension models — verify column definitions and relationships."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.modules.security_master.models import (
    FixedIncomeExtensionRecord,
    FutureExtensionRecord,
    FXExtensionRecord,
    OptionExtensionRecord,
    SwapExtensionRecord,
)


class TestFixedIncomeExtension:
    def test_create_with_all_fields(self) -> None:
        ext = FixedIncomeExtensionRecord(
            instrument_id="00000000-0000-0000-0000-000000000001",
            coupon_rate=Decimal("0.045000"),
            coupon_frequency=2,
            maturity_date=date(2034, 6, 15),
            issue_date=date(2024, 6, 15),
            face_value=Decimal("1000.00"),
            day_count_convention="30/360",
            credit_rating="AA-",
            issuer="US Treasury",
            seniority="senior",
            callable=False,
            putable=False,
        )
        assert ext.coupon_rate == Decimal("0.045000")
        assert ext.coupon_frequency == 2
        assert ext.maturity_date == date(2034, 6, 15)
        assert ext.credit_rating == "AA-"
        assert ext.callable is False

    def test_create_minimal(self) -> None:
        ext = FixedIncomeExtensionRecord(
            instrument_id="00000000-0000-0000-0000-000000000002",
        )
        assert ext.coupon_rate is None
        assert ext.maturity_date is None

    def test_table_name(self) -> None:
        assert FixedIncomeExtensionRecord.__tablename__ == "fixed_income_extensions"
        assert FixedIncomeExtensionRecord.__table_args__["schema"] == "security_master"


class TestOptionExtension:
    def test_create_call_option(self) -> None:
        ext = OptionExtensionRecord(
            instrument_id="00000000-0000-0000-0000-000000000010",
            underlying_id="00000000-0000-0000-0000-000000000001",
            option_type="CALL",
            exercise_style="european",
            strike_price=Decimal("150.000000"),
            expiry_date=date(2026, 12, 20),
            contract_size=Decimal("100.0000"),
            settlement_type="cash",
        )
        assert ext.option_type == "CALL"
        assert ext.strike_price == Decimal("150.000000")
        assert ext.exercise_style == "european"

    def test_table_name(self) -> None:
        assert OptionExtensionRecord.__tablename__ == "option_extensions"


class TestFutureExtension:
    def test_create_with_margins(self) -> None:
        ext = FutureExtensionRecord(
            instrument_id="00000000-0000-0000-0000-000000000020",
            contract_size=Decimal("50.0000"),
            tick_size=Decimal("0.25000000"),
            tick_value=Decimal("12.5000"),
            margin_initial=Decimal("15000.00"),
            margin_maintenance=Decimal("12000.00"),
            settlement_type="cash",
            expiry_date=date(2026, 9, 20),
        )
        assert ext.margin_initial == Decimal("15000.00")
        assert ext.tick_size == Decimal("0.25000000")

    def test_table_name(self) -> None:
        assert FutureExtensionRecord.__tablename__ == "future_extensions"


class TestFXExtension:
    def test_create_currency_pair(self) -> None:
        ext = FXExtensionRecord(
            instrument_id="00000000-0000-0000-0000-000000000030",
            base_currency="EUR",
            quote_currency="USD",
            pip_size=Decimal("0.00010000"),
            lot_size=100_000,
            settlement_days=2,
        )
        assert ext.base_currency == "EUR"
        assert ext.quote_currency == "USD"
        assert ext.settlement_days == 2

    def test_table_name(self) -> None:
        assert FXExtensionRecord.__tablename__ == "fx_extensions"


class TestSwapExtension:
    def test_create_interest_rate_swap(self) -> None:
        ext = SwapExtensionRecord(
            instrument_id="00000000-0000-0000-0000-000000000040",
            swap_type="interest_rate",
            notional_currency="USD",
            fixed_rate=Decimal("0.035000"),
            floating_index="SOFR",
            floating_spread=Decimal("0.001500"),
            payment_frequency="quarterly",
            day_count_convention="ACT/360",
            effective_date=date(2026, 1, 15),
            maturity_date=date(2031, 1, 15),
        )
        assert ext.swap_type == "interest_rate"
        assert ext.floating_index == "SOFR"
        assert ext.fixed_rate == Decimal("0.035000")

    def test_table_name(self) -> None:
        assert SwapExtensionRecord.__tablename__ == "swap_extensions"
