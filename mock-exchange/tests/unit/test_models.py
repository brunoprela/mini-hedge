"""Pydantic model serialization roundtrip tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from mock_exchange.shared.models import (
    FillReport,
    InstrumentInfo,
    OrderAck,
    PriceQuote,
    ScenarioStatus,
)


class TestPriceQuoteRoundtrip:
    def test_model_dump_roundtrip(self) -> None:
        original = PriceQuote(
            instrument_id="AAPL",
            bid=Decimal("189.50"),
            ask=Decimal("190.50"),
            mid=Decimal("190.00"),
            volume=10000,
            timestamp=datetime.now(UTC),
        )
        dumped = original.model_dump()
        restored = PriceQuote(**dumped)
        assert restored == original

    def test_json_roundtrip(self) -> None:
        original = PriceQuote(
            instrument_id="AAPL",
            bid=Decimal("189.50"),
            ask=Decimal("190.50"),
            mid=Decimal("190.00"),
            volume=10000,
            timestamp=datetime.now(UTC),
        )
        json_str = original.model_dump_json()
        restored = PriceQuote.model_validate_json(json_str)
        assert restored.instrument_id == original.instrument_id
        assert restored.mid == original.mid


class TestInstrumentInfoRoundtrip:
    def test_model_dump_roundtrip(self) -> None:
        original = InstrumentInfo(
            ticker="AAPL",
            name="Apple Inc.",
            asset_class="equity",
            currency="USD",
            exchange="NASDAQ",
            country="US",
            sector="Technology",
            industry="Consumer Electronics",
        )
        dumped = original.model_dump()
        restored = InstrumentInfo(**dumped)
        assert restored == original

    def test_defaults(self) -> None:
        info = InstrumentInfo(
            ticker="X",
            name="X Corp",
            asset_class="equity",
            currency="USD",
            exchange="NYSE",
            country="US",
            sector="Tech",
            industry="Software",
        )
        assert info.annual_drift == 0.08
        assert info.annual_volatility == 0.25
        assert info.spread_bps == 10.0
        assert info.is_active is True


class TestOrderAckRoundtrip:
    def test_model_dump_roundtrip(self) -> None:
        original = OrderAck(
            exchange_order_id="ex-001",
            client_order_id="cl-001",
            status="acknowledged",
            received_at=datetime.now(UTC),
        )
        dumped = original.model_dump()
        restored = OrderAck(**dumped)
        assert restored == original


class TestFillReportRoundtrip:
    def test_model_dump_roundtrip(self) -> None:
        original = FillReport(
            fill_id="f-001",
            exchange_order_id="ex-001",
            client_order_id="cl-001",
            instrument_id="AAPL",
            side="buy",
            quantity=Decimal("100"),
            price=Decimal("150.00"),
            filled_at=datetime.now(UTC),
        )
        dumped = original.model_dump()
        restored = FillReport(**dumped)
        assert restored == original


class TestScenarioStatusRoundtrip:
    def test_model_dump_roundtrip(self) -> None:
        original = ScenarioStatus(
            active_scenario="calm",
            instruments=42,
            phase="steady",
            uptime_seconds=123.4,
        )
        dumped = original.model_dump()
        restored = ScenarioStatus(**dumped)
        assert restored == original

    def test_defaults(self) -> None:
        status = ScenarioStatus()
        assert status.active_scenario is None
        assert status.instruments == 0
        assert status.phase is None
        assert status.uptime_seconds == 0.0
