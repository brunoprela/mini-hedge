"""Unit tests for TradeRequest model including idempotency key."""

from decimal import Decimal
from uuid import uuid4

from app.modules.positions.interface import TradeRequest, TradeSide


class TestTradeRequest:
    def test_without_idempotency_key(self) -> None:
        req = TradeRequest(
            portfolio_id=uuid4(),
            instrument_id="AAPL",
            side=TradeSide.BUY,
            quantity=Decimal("100"),
            price=Decimal("150.00"),
        )
        assert req.idempotency_key is None

    def test_with_idempotency_key(self) -> None:
        key = "trade-abc-123"
        req = TradeRequest(
            portfolio_id=uuid4(),
            instrument_id="AAPL",
            side=TradeSide.BUY,
            quantity=Decimal("100"),
            price=Decimal("150.00"),
            idempotency_key=key,
        )
        assert req.idempotency_key == key

    def test_default_currency(self) -> None:
        req = TradeRequest(
            portfolio_id=uuid4(),
            instrument_id="AAPL",
            side=TradeSide.SELL,
            quantity=Decimal("50"),
            price=Decimal("200.00"),
        )
        assert req.currency == "USD"
