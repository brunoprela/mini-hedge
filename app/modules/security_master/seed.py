"""Seed instrument reference data for local development."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.modules.security_master.models import EquityExtensionRecord, InstrumentRecord

# Each entry contains instrument fields + an optional "shares_outstanding"
# that seeds the equity_extensions table.
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

# Fields that belong on equity_extensions, not on the base instrument.
_EQUITY_EXTENSION_FIELDS = {"shares_outstanding"}


def build_seed_records() -> tuple[list[InstrumentRecord], list[EquityExtensionRecord]]:
    """Return (instruments, equity_extensions) seed records."""
    instruments: list[InstrumentRecord] = []
    extensions: list[EquityExtensionRecord] = []

    for data in SEED_INSTRUMENTS:
        instrument_id = str(uuid4())

        # Split extension fields from base instrument fields
        ext_data = {k: data[k] for k in _EQUITY_EXTENSION_FIELDS if k in data}
        instr_data = {k: v for k, v in data.items() if k not in _EQUITY_EXTENSION_FIELDS}

        instruments.append(InstrumentRecord(id=instrument_id, **instr_data))

        if ext_data:
            extensions.append(EquityExtensionRecord(instrument_id=instrument_id, **ext_data))

    return instruments, extensions
