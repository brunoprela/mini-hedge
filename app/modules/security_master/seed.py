"""Seed instrument reference data for local development."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.modules.security_master.models import InstrumentRecord

SEED_INSTRUMENTS: list[dict[str, object]] = [
    {
        "name": "Apple Inc.",
        "ticker": "AAPL",
        "asset_class": "equity",
        "currency": "USD",
        "exchange": "NASDAQ",
        "country": "US",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "shares_outstanding": Decimal("15_000_000_000"),
        "listed_date": date(1980, 12, 12),
    },
    {
        "name": "Microsoft Corporation",
        "ticker": "MSFT",
        "asset_class": "equity",
        "currency": "USD",
        "exchange": "NASDAQ",
        "country": "US",
        "sector": "Technology",
        "industry": "Software",
        "shares_outstanding": Decimal("7_400_000_000"),
        "listed_date": date(1986, 3, 13),
    },
    {
        "name": "Alphabet Inc.",
        "ticker": "GOOGL",
        "asset_class": "equity",
        "currency": "USD",
        "exchange": "NASDAQ",
        "country": "US",
        "sector": "Technology",
        "industry": "Internet Services",
        "shares_outstanding": Decimal("12_200_000_000"),
        "listed_date": date(2004, 8, 19),
    },
    {
        "name": "Amazon.com Inc.",
        "ticker": "AMZN",
        "asset_class": "equity",
        "currency": "USD",
        "exchange": "NASDAQ",
        "country": "US",
        "sector": "Consumer Discretionary",
        "industry": "E-Commerce",
        "shares_outstanding": Decimal("10_300_000_000"),
        "listed_date": date(1997, 5, 15),
    },
    {
        "name": "JPMorgan Chase & Co.",
        "ticker": "JPM",
        "asset_class": "equity",
        "currency": "USD",
        "exchange": "NYSE",
        "country": "US",
        "sector": "Financials",
        "industry": "Banking",
        "shares_outstanding": Decimal("2_900_000_000"),
        "listed_date": date(1969, 3, 5),
    },
    {
        "name": "Goldman Sachs Group Inc.",
        "ticker": "GS",
        "asset_class": "equity",
        "currency": "USD",
        "exchange": "NYSE",
        "country": "US",
        "sector": "Financials",
        "industry": "Investment Banking",
        "shares_outstanding": Decimal("340_000_000"),
        "listed_date": date(1999, 5, 4),
    },
    {
        "name": "Johnson & Johnson",
        "ticker": "JNJ",
        "asset_class": "equity",
        "currency": "USD",
        "exchange": "NYSE",
        "country": "US",
        "sector": "Healthcare",
        "industry": "Pharmaceuticals",
        "shares_outstanding": Decimal("2_400_000_000"),
        "listed_date": date(1944, 9, 25),
    },
    {
        "name": "Exxon Mobil Corporation",
        "ticker": "XOM",
        "asset_class": "equity",
        "currency": "USD",
        "exchange": "NYSE",
        "country": "US",
        "sector": "Energy",
        "industry": "Oil & Gas",
        "shares_outstanding": Decimal("4_200_000_000"),
        "listed_date": date(1920, 1, 1),
    },
    {
        "name": "Tesla Inc.",
        "ticker": "TSLA",
        "asset_class": "equity",
        "currency": "USD",
        "exchange": "NASDAQ",
        "country": "US",
        "sector": "Consumer Discretionary",
        "industry": "Automobiles",
        "shares_outstanding": Decimal("3_200_000_000"),
        "listed_date": date(2010, 6, 29),
    },
    {
        "name": "NVIDIA Corporation",
        "ticker": "NVDA",
        "asset_class": "equity",
        "currency": "USD",
        "exchange": "NASDAQ",
        "country": "US",
        "sector": "Technology",
        "industry": "Semiconductors",
        "shares_outstanding": Decimal("24_600_000_000"),
        "listed_date": date(1999, 1, 22),
    },
]


def build_seed_records() -> list[InstrumentRecord]:
    records = []
    for data in SEED_INSTRUMENTS:
        records.append(
            InstrumentRecord(
                id=str(uuid4()),
                **data,  # type: ignore[arg-type]
            )
        )
    return records
