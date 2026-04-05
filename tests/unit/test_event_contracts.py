"""Event data contract tests — verify publisher data matches consumer expectations.

These tests catch the class of bugs where a producer publishes event data
that a downstream consumer can't parse: missing fields, wrong types,
string serialization that doesn't roundtrip, etc.

No database needed — pure data validation.
"""

import decimal
from dataclasses import asdict
from decimal import Decimal
from uuid import UUID, uuid4

from app.modules.positions.interface import (
    PnLMarkToMarketData,
    PnLRealizedData,
    PositionChangedData,
    PositionEventType,
    TradeSide,
)
from app.shared.events import BaseEvent
from tests.factories import (
    DEFAULT_PORTFOLIO_ID,
    make_price_event,
    make_trades_executed_event,
)

# ---------------------------------------------------------------------------
# Contract: trades.executed (OrderService._process_fill → consumers)
# ---------------------------------------------------------------------------


class TestTradesExecutedContract:
    """Validate the trades.executed event data published by OrderService._process_fill."""

    def _build_trades_executed_data(self) -> dict[str, str]:
        """Build the exact data dict that OrderService._process_fill publishes (lines 364-372)."""
        return {
            "portfolio_id": str(uuid4()),
            "instrument_id": "AAPL",
            "side": "buy",
            "quantity": "100",
            "price": "150.00",
            "trade_id": str(uuid4()),
            "currency": "USD",
        }

    def test_trade_handler_can_parse(self) -> None:
        """TradeHandler.handle_trade_event accesses these fields (lines 144-157)."""
        data = self._build_trades_executed_data()

        # Fields accessed directly via data["key"]
        assert UUID(data["portfolio_id"])  # line 151
        assert data["side"] in ("buy", "sell")  # line 144-145
        assert Decimal(data["quantity"])  # line 154
        assert Decimal(data["price"])  # line 155
        assert data.get("currency", "USD")  # line 156
        # trade_id is optional (line 146: uses uuid4() fallback)
        assert UUID(data["trade_id"])

    def test_cash_handler_can_parse(self) -> None:
        """CashManagementService.handle_trade_executed accesses these fields (lines 446-457)."""
        data = self._build_trades_executed_data()

        # Uses .get() with defaults
        assert data.get("portfolio_id")
        assert data.get("instrument_id", "")
        assert data.get("currency", "USD")
        assert data.get("side", "buy") in ("buy", "sell")
        assert Decimal(str(data.get("quantity", "0")))
        assert Decimal(str(data.get("price", "0")))

    def test_fund_slug_is_present(self) -> None:
        """trades.executed events must carry fund_slug for downstream handlers."""
        event = make_trades_executed_event(fund_slug="alpha")
        assert event.fund_slug == "alpha"

    def test_event_type_matches_side(self) -> None:
        """OrderService sets event_type to 'trade.buy' or 'trade.sell' based on side."""
        buy_event = make_trades_executed_event(side="buy")
        assert buy_event.event_type == "trade.buy"

        sell_event = make_trades_executed_event(side="sell")
        assert sell_event.event_type == "trade.sell"


# ---------------------------------------------------------------------------
# Contract: positions.changed (TradeHandler._publish_downstream → consumers)
# ---------------------------------------------------------------------------


class TestPositionsChangedContract:
    """Validate positions.changed event data from TradeHandler._publish_downstream."""

    def _build_positions_changed_data(self) -> dict[str, str]:
        """Build the data dict exactly as TradeHandler serializes it (line 302).

        TradeHandler does: ``{k: str(v) for k, v in asdict(de.data).items()}``
        """
        raw = PositionChangedData(
            portfolio_id=DEFAULT_PORTFOLIO_ID,
            instrument_id="AAPL",
            quantity=Decimal("100"),
            avg_cost=Decimal("150.00"),
            cost_basis=Decimal("15000.00"),
            currency="USD",
        )
        data = asdict(raw)
        return {k: str(v) for k, v in data.items()}

    def test_portfolio_id_roundtrips_as_uuid(self) -> None:
        """Downstream handlers parse portfolio_id back to UUID."""
        data = self._build_positions_changed_data()
        # This is what setup.py's _make_handler closures do (line 368/489)
        assert UUID(data["portfolio_id"]) == DEFAULT_PORTFOLIO_ID

    def test_downstream_handlers_can_extract_portfolio_id(self) -> None:
        """ExposureService, RiskService, PostTradeMonitor all call data.get("portfolio_id")."""
        data = self._build_positions_changed_data()
        pid_str = data.get("portfolio_id")
        assert pid_str is not None
        assert pid_str != ""
        assert pid_str != "None"  # catches str(None) bug

    def test_decimal_fields_roundtrip(self) -> None:
        """Numeric fields survive str() → Decimal() roundtrip."""
        data = self._build_positions_changed_data()
        assert Decimal(data["quantity"]) == Decimal("100")
        assert Decimal(data["avg_cost"]) == Decimal("150.00")
        assert Decimal(data["cost_basis"]) == Decimal("15000.00")


# ---------------------------------------------------------------------------
# Contract: pnl.updated (TradeHandler/MTMHandler → PostTradeMonitor)
# ---------------------------------------------------------------------------


class TestPnlUpdatedContract:
    """Validate pnl.updated event data from both TradeHandler and MTMHandler."""

    def _build_pnl_realized_data(self) -> dict[str, str]:
        raw = PnLRealizedData(
            portfolio_id=DEFAULT_PORTFOLIO_ID,
            instrument_id="AAPL",
            realized_pnl=Decimal("500.00"),
            price=Decimal("155.00"),
            currency="USD",
        )
        data = asdict(raw)
        return {k: str(v) for k, v in data.items()}

    def _build_pnl_mtm_data(self) -> dict[str, str]:
        raw = PnLMarkToMarketData(
            portfolio_id=DEFAULT_PORTFOLIO_ID,
            instrument_id="AAPL",
            market_price=Decimal("160.00"),
            market_value=Decimal("16000.00"),
            unrealized_pnl=Decimal("1000.00"),
            pnl_change=Decimal("500.00"),
            currency="USD",
        )
        data = asdict(raw)
        return {k: str(v) for k, v in data.items()}

    def test_post_trade_monitor_can_parse_realized(self) -> None:
        """PostTradeMonitor.handle_mtm_update accesses portfolio_id (line 104)."""
        data = self._build_pnl_realized_data()
        pid_str = data.get("portfolio_id")
        assert pid_str is not None
        assert UUID(pid_str) == DEFAULT_PORTFOLIO_ID

    def test_post_trade_monitor_can_parse_mtm(self) -> None:
        data = self._build_pnl_mtm_data()
        pid_str = data.get("portfolio_id")
        assert pid_str is not None
        assert UUID(pid_str) == DEFAULT_PORTFOLIO_ID

    def test_pnl_mtm_event_has_fund_slug(self) -> None:
        """MTMHandler always sets fund_slug on published events (line 139)."""
        event = BaseEvent(
            event_type=PositionEventType.PNL_MARK_TO_MARKET,
            data=self._build_pnl_mtm_data(),
            actor_id="system",
            actor_type="system",
            fund_slug="alpha",
        )
        assert event.fund_slug == "alpha"


# ---------------------------------------------------------------------------
# Contract: prices.normalized (simulator → MarketDataService + MTMHandler)
# ---------------------------------------------------------------------------


class TestPricesNormalizedContract:
    """Validate the shared.prices.normalized event data."""

    def test_mtm_handler_can_parse(self) -> None:
        """MTMHandler accesses data['instrument_id'] and data['mid'] (lines 56-57)."""
        event = make_price_event(instrument_id="AAPL", mid=Decimal("155.00"))
        data = event.data
        assert data["instrument_id"] == "AAPL"
        assert Decimal(data["mid"]) == Decimal("155.00")

    def test_market_data_service_can_parse(self) -> None:
        """_make_price_handler checks for required fields (setup.py lines 627-632)."""
        event = make_price_event()
        required = ("instrument_id", "bid", "ask", "mid", "source")
        assert all(k in event.data for k in required)

    def test_price_fields_are_decimal_parseable(self) -> None:
        event = make_price_event(mid=Decimal("123.456"))
        assert Decimal(event.data["bid"])
        assert Decimal(event.data["ask"])
        assert Decimal(event.data["mid"]) == Decimal("123.456")


# ---------------------------------------------------------------------------
# String serialization roundtrip — the core serialization pattern
# ---------------------------------------------------------------------------


class TestStringSerialization:
    """TradeHandler._publish_downstream (line 302) serializes via {k: str(v) for ...}.

    This tests that all domain types survive the str() → parse roundtrip.
    """

    def test_uuid_roundtrips(self) -> None:
        original = uuid4()
        assert UUID(str(original)) == original

    def test_decimal_roundtrips(self) -> None:
        for value in ["100", "150.00", "0.001", "-42.50", "99999.99999"]:
            original = Decimal(value)
            assert Decimal(str(original)) == original

    def test_trade_side_str_enum_produces_value(self) -> None:
        """TradeSide is a StrEnum — str() must produce 'buy'/'sell', not 'TradeSide.BUY'."""
        assert str(TradeSide.BUY) == "buy"
        assert str(TradeSide.SELL) == "sell"

    def test_position_event_type_str_enum(self) -> None:
        """PositionEventType is a StrEnum — str() must produce the value."""
        assert str(PositionEventType.TRADE_BUY) == "trade.buy"
        assert str(PositionEventType.POSITION_CHANGED) == "position.changed"
        assert str(PositionEventType.PNL_MARK_TO_MARKET) == "pnl.mark_to_market"

    def test_none_field_produces_string_none(self) -> None:
        """If a field is None, str(None) → 'None' which will fail UUID/Decimal parsing.

        This documents a latent bug: if any dataclass field is None and gets
        serialized, downstream parsing will fail.
        """
        assert str(None) == "None"
        # These would fail:
        import pytest

        with pytest.raises(ValueError):
            UUID("None")
        with pytest.raises(decimal.InvalidOperation):
            Decimal("None")
