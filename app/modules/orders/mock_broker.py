"""Mock broker adapter — simulates immediate fills for dev/test."""

from __future__ import annotations

import random
from decimal import Decimal

import structlog

logger = structlog.get_logger()


class MockBrokerAdapter:
    """Simulates immediate fill at requested price with small random slippage."""

    async def submit_order(
        self,
        instrument_id: str,
        side: str,
        quantity: Decimal,
        price: Decimal | None = None,
    ) -> tuple[Decimal, Decimal]:
        """Submit order and return (fill_price, fill_quantity).

        For market orders (price=None), uses a synthetic price.
        Applies small random slippage (0-0.1%).
        """
        base_price = price or Decimal("100.00")
        slippage = Decimal(str(random.uniform(-0.001, 0.001)))
        fill_price = base_price * (1 + slippage)
        fill_price = fill_price.quantize(Decimal("0.01"))
        logger.info(
            "mock_broker_fill",
            instrument=instrument_id,
            side=side,
            quantity=str(quantity),
            fill_price=str(fill_price),
        )
        return fill_price, quantity
