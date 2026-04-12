"""Seed data for market data — FX rates and latest instrument prices."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from app.modules.market_data.interfaces import FXRateSnapshot, PriceSnapshot

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.shared.database import TenantSessionFactory

logger = structlog.get_logger()

# Major FX rates (USD-based: 1 USD = rate in quote currency)
_FX_RATES: list[tuple[str, str, Decimal]] = [
    ("USD", "EUR", Decimal("0.9230")),
    ("USD", "GBP", Decimal("0.7920")),
    ("USD", "JPY", Decimal("151.50")),
    ("USD", "CHF", Decimal("0.8815")),
    ("USD", "CAD", Decimal("1.3640")),
    ("USD", "AUD", Decimal("1.5380")),
    ("EUR", "USD", Decimal("1.0835")),
    ("GBP", "USD", Decimal("1.2625")),
    ("EUR", "GBP", Decimal("0.8585")),
    ("EUR", "CHF", Decimal("0.9550")),
]

# Sample instrument prices — covers the most commonly held positions
_PRICES: list[tuple[str, Decimal, Decimal, Decimal, Decimal]] = [
    # (instrument_id, bid, ask, mid, volume)
    ("AAPL", Decimal("248.50"), Decimal("248.75"), Decimal("248.625"), Decimal("45000000")),
    ("MSFT", Decimal("415.20"), Decimal("415.55"), Decimal("415.375"), Decimal("22000000")),
    ("GOOGL", Decimal("172.80"), Decimal("173.05"), Decimal("172.925"), Decimal("18000000")),
    ("AMZN", Decimal("198.30"), Decimal("198.60"), Decimal("198.450"), Decimal("35000000")),
    ("NVDA", Decimal("875.00"), Decimal("876.50"), Decimal("875.750"), Decimal("55000000")),
    ("META", Decimal("510.25"), Decimal("510.75"), Decimal("510.500"), Decimal("15000000")),
    ("JPM", Decimal("198.40"), Decimal("198.70"), Decimal("198.550"), Decimal("8000000")),
    ("V", Decimal("282.10"), Decimal("282.45"), Decimal("282.275"), Decimal("6000000")),
    ("JNJ", Decimal("158.30"), Decimal("158.55"), Decimal("158.425"), Decimal("5000000")),
    ("UNH", Decimal("520.80"), Decimal("521.40"), Decimal("521.100"), Decimal("3500000")),
    ("PG", Decimal("168.90"), Decimal("169.15"), Decimal("169.025"), Decimal("4500000")),
    ("HD", Decimal("378.50"), Decimal("379.00"), Decimal("378.750"), Decimal("3000000")),
    ("BAC", Decimal("38.20"), Decimal("38.30"), Decimal("38.250"), Decimal("30000000")),
    ("XOM", Decimal("112.40"), Decimal("112.65"), Decimal("112.525"), Decimal("12000000")),
    ("DIS", Decimal("108.70"), Decimal("108.95"), Decimal("108.825"), Decimal("8000000")),
    ("TSLA", Decimal("245.30"), Decimal("246.00"), Decimal("245.650"), Decimal("65000000")),
    ("GS", Decimal("485.20"), Decimal("486.00"), Decimal("485.600"), Decimal("2500000")),
    ("MS", Decimal("98.40"), Decimal("98.65"), Decimal("98.525"), Decimal("5000000")),
    ("INTC", Decimal("31.20"), Decimal("31.35"), Decimal("31.275"), Decimal("25000000")),
    ("KO", Decimal("62.40"), Decimal("62.55"), Decimal("62.475"), Decimal("9000000")),
]


async def seed_dev_data(app: FastAPI, sf: TenantSessionFactory) -> None:
    """Idempotent dev-only seeding for market data (FX rates + prices)."""
    market_data_service = getattr(app.state, "market_data_service", None)
    if market_data_service is None:
        logger.debug("market_data_seed_skipped", reason="service not available")
        return

    now = datetime.now(UTC)

    # Seed FX rates — always update in-memory cache, persist if no DB row exists
    fx_seeded = 0
    for base, quote, rate in _FX_RATES:
        snapshot = FXRateSnapshot(
            base_currency=base,
            quote_currency=quote,
            rate=rate,
            timestamp=now,
            source="seed",
        )
        # Always update in-memory cache so FX conversion works immediately
        market_data_service.update_fx_rate(snapshot)
        try:
            await market_data_service.store_fx_rate(snapshot)
            fx_seeded += 1
        except Exception:
            # Duplicate key or other DB issue — in-memory cache is updated, move on
            pass

    # Seed instrument prices
    price_seeded = 0
    for instrument_id, bid, ask, mid, volume in _PRICES:
        # Check in-memory cache first
        cached = market_data_service._latest.get(instrument_id)
        if cached is not None:
            continue

        snapshot = PriceSnapshot(
            instrument_id=instrument_id,
            bid=bid,
            ask=ask,
            mid=mid,
            volume=volume,
            timestamp=now,
            source="seed",
        )
        market_data_service.update_latest(snapshot)
        try:
            await market_data_service.store_price(snapshot)
            price_seeded += 1
        except Exception:
            # Duplicate key or other DB issue — in-memory is updated, move on
            pass

    if fx_seeded or price_seeded:
        logger.info(
            "market_data_seed_complete",
            fx_rates=fx_seeded,
            prices=price_seeded,
        )
    else:
        logger.debug("market_data_seed_skipped", reason="data already exists")
