"""Unit tests for VolatilitySurface model and repository structure."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from app.modules.market_data.models.volatility_surface import VolatilitySurfaceRecord


class TestVolatilitySurfaceModel:
    def test_create_record(self) -> None:
        record = VolatilitySurfaceRecord(
            timestamp=datetime(2026, 4, 12, 14, 0, 0, tzinfo=UTC),
            instrument_id="AAPL",
            expiry=date(2026, 12, 20),
            strike=Decimal("200.0000"),
            implied_vol=Decimal("0.250000"),
            delta=Decimal("0.450000"),
            source="bloomberg",
        )
        assert record.instrument_id == "AAPL"
        assert record.implied_vol == Decimal("0.250000")
        assert record.delta == Decimal("0.450000")
        assert record.expiry == date(2026, 12, 20)

    def test_nullable_delta(self) -> None:
        record = VolatilitySurfaceRecord(
            timestamp=datetime(2026, 4, 12, 14, 0, 0, tzinfo=UTC),
            instrument_id="SPX",
            expiry=date(2026, 12, 20),
            strike=Decimal("5500.0000"),
            implied_vol=Decimal("0.180000"),
            delta=None,
            source="cboe",
        )
        assert record.delta is None

    def test_table_name_and_schema(self) -> None:
        assert VolatilitySurfaceRecord.__tablename__ == "volatility_surfaces"
        assert VolatilitySurfaceRecord.__table_args__[2]["schema"] == "market_data"
