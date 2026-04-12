"""Seed instrument reference data for local development."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from app.modules.security_master.models.equity_extension import EquityExtensionRecord
from app.modules.security_master.models.fixed_income_extension import FixedIncomeExtensionRecord
from app.modules.security_master.models.future_extension import FutureExtensionRecord
from app.modules.security_master.models.fx_extension import FXExtensionRecord
from app.modules.security_master.models.instrument import InstrumentRecord
from app.modules.security_master.models.option_extension import OptionExtensionRecord
from app.modules.security_master.models.swap_extension import SwapExtensionRecord
from app.shared.types import AssetClass

if TYPE_CHECKING:
    from app.shared.adapters.reference_data import ExternalInstrument

# Each entry contains instrument fields + an optional "shares_outstanding"
# that seeds the equity_extensions table.
SEED_INSTRUMENTS: list[dict[str, object]] = [
    # --- US Technology ---
    {
        "name": "Apple Inc.",
        "ticker": "AAPL",
        "asset_class": AssetClass.EQUITY,
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
        "asset_class": AssetClass.EQUITY,
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
        "asset_class": AssetClass.EQUITY,
        "currency": "USD",
        "exchange": "NASDAQ",
        "country": "US",
        "sector": "Technology",
        "industry": "Internet Services",
        "shares_outstanding": Decimal("12_200_000_000"),
        "listed_date": date(2004, 8, 19),
    },
    {
        "name": "NVIDIA Corporation",
        "ticker": "NVDA",
        "asset_class": AssetClass.EQUITY,
        "currency": "USD",
        "exchange": "NASDAQ",
        "country": "US",
        "sector": "Technology",
        "industry": "Semiconductors",
        "shares_outstanding": Decimal("24_600_000_000"),
        "listed_date": date(1999, 1, 22),
    },
    # --- US Consumer Discretionary ---
    {
        "name": "Amazon.com Inc.",
        "ticker": "AMZN",
        "asset_class": AssetClass.EQUITY,
        "currency": "USD",
        "exchange": "NASDAQ",
        "country": "US",
        "sector": "Consumer Discretionary",
        "industry": "E-Commerce",
        "shares_outstanding": Decimal("10_300_000_000"),
        "listed_date": date(1997, 5, 15),
    },
    {
        "name": "Tesla Inc.",
        "ticker": "TSLA",
        "asset_class": AssetClass.EQUITY,
        "currency": "USD",
        "exchange": "NASDAQ",
        "country": "US",
        "sector": "Consumer Discretionary",
        "industry": "Automobiles",
        "shares_outstanding": Decimal("3_200_000_000"),
        "listed_date": date(2010, 6, 29),
    },
    # --- US Financials ---
    {
        "name": "JPMorgan Chase & Co.",
        "ticker": "JPM",
        "asset_class": AssetClass.EQUITY,
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
        "asset_class": AssetClass.EQUITY,
        "currency": "USD",
        "exchange": "NYSE",
        "country": "US",
        "sector": "Financials",
        "industry": "Investment Banking",
        "shares_outstanding": Decimal("340_000_000"),
        "listed_date": date(1999, 5, 4),
    },
    # --- US Healthcare ---
    {
        "name": "Johnson & Johnson",
        "ticker": "JNJ",
        "asset_class": AssetClass.EQUITY,
        "currency": "USD",
        "exchange": "NYSE",
        "country": "US",
        "sector": "Healthcare",
        "industry": "Pharmaceuticals",
        "shares_outstanding": Decimal("2_400_000_000"),
        "listed_date": date(1944, 9, 25),
    },
    {
        "name": "UnitedHealth Group Inc.",
        "ticker": "UNH",
        "asset_class": AssetClass.EQUITY,
        "currency": "USD",
        "exchange": "NYSE",
        "country": "US",
        "sector": "Healthcare",
        "industry": "Managed Healthcare",
        "shares_outstanding": Decimal("920_000_000"),
        "listed_date": date(1984, 10, 17),
    },
    # --- US Energy ---
    {
        "name": "Exxon Mobil Corporation",
        "ticker": "XOM",
        "asset_class": AssetClass.EQUITY,
        "currency": "USD",
        "exchange": "NYSE",
        "country": "US",
        "sector": "Energy",
        "industry": "Oil & Gas",
        "shares_outstanding": Decimal("4_200_000_000"),
        "listed_date": date(1920, 1, 1),
    },
    # --- UK ---
    {
        "name": "AstraZeneca PLC",
        "ticker": "AZN",
        "asset_class": AssetClass.EQUITY,
        "currency": "GBP",
        "exchange": "LSE",
        "country": "GB",
        "sector": "Healthcare",
        "industry": "Pharmaceuticals",
        "shares_outstanding": Decimal("1_560_000_000"),
        "listed_date": date(1999, 4, 6),
    },
    {
        "name": "HSBC Holdings PLC",
        "ticker": "HSBA",
        "asset_class": AssetClass.EQUITY,
        "currency": "GBP",
        "exchange": "LSE",
        "country": "GB",
        "sector": "Financials",
        "industry": "Banking",
        "shares_outstanding": Decimal("19_700_000_000"),
        "listed_date": date(1991, 7, 12),
    },
    {
        "name": "Shell PLC",
        "ticker": "SHEL",
        "asset_class": AssetClass.EQUITY,
        "currency": "GBP",
        "exchange": "LSE",
        "country": "GB",
        "sector": "Energy",
        "industry": "Oil & Gas",
        "shares_outstanding": Decimal("6_800_000_000"),
        "listed_date": date(2005, 7, 20),
    },
    {
        "name": "Unilever PLC",
        "ticker": "ULVR",
        "asset_class": AssetClass.EQUITY,
        "currency": "GBP",
        "exchange": "LSE",
        "country": "GB",
        "sector": "Consumer Staples",
        "industry": "Personal Products",
        "shares_outstanding": Decimal("2_500_000_000"),
        "listed_date": date(1929, 1, 1),
    },
    # --- Germany ---
    {
        "name": "SAP SE",
        "ticker": "SAP",
        "asset_class": AssetClass.EQUITY,
        "currency": "EUR",
        "exchange": "XETRA",
        "country": "DE",
        "sector": "Technology",
        "industry": "Enterprise Software",
        "shares_outstanding": Decimal("1_220_000_000"),
        "listed_date": date(1988, 11, 4),
    },
    {
        "name": "Siemens AG",
        "ticker": "SIE",
        "asset_class": AssetClass.EQUITY,
        "currency": "EUR",
        "exchange": "XETRA",
        "country": "DE",
        "sector": "Industrials",
        "industry": "Industrial Conglomerates",
        "shares_outstanding": Decimal("800_000_000"),
        "listed_date": date(1897, 1, 1),
    },
    # --- France ---
    {
        "name": "LVMH Moët Hennessy",
        "ticker": "MC",
        "asset_class": AssetClass.EQUITY,
        "currency": "EUR",
        "exchange": "EURONEXT",
        "country": "FR",
        "sector": "Consumer Discretionary",
        "industry": "Luxury Goods",
        "shares_outstanding": Decimal("502_000_000"),
        "listed_date": date(1987, 6, 1),
    },
    {
        "name": "TotalEnergies SE",
        "ticker": "TTE",
        "asset_class": AssetClass.EQUITY,
        "currency": "EUR",
        "exchange": "EURONEXT",
        "country": "FR",
        "sector": "Energy",
        "industry": "Oil & Gas",
        "shares_outstanding": Decimal("2_350_000_000"),
        "listed_date": date(1929, 3, 28),
    },
    # --- Japan ---
    {
        "name": "Toyota Motor Corporation",
        "ticker": "7203",
        "asset_class": AssetClass.EQUITY,
        "currency": "JPY",
        "exchange": "TSE",
        "country": "JP",
        "sector": "Consumer Discretionary",
        "industry": "Automobiles",
        "shares_outstanding": Decimal("13_370_000_000"),
        "listed_date": date(1949, 5, 16),
    },
    {
        "name": "Sony Group Corporation",
        "ticker": "6758",
        "asset_class": AssetClass.EQUITY,
        "currency": "JPY",
        "exchange": "TSE",
        "country": "JP",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "shares_outstanding": Decimal("1_240_000_000"),
        "listed_date": date(1958, 12, 1),
    },
    # --- Switzerland ---
    {
        "name": "Nestlé S.A.",
        "ticker": "NESN",
        "asset_class": AssetClass.EQUITY,
        "currency": "CHF",
        "exchange": "SIX",
        "country": "CH",
        "sector": "Consumer Staples",
        "industry": "Food Products",
        "shares_outstanding": Decimal("2_700_000_000"),
        "listed_date": date(1905, 1, 1),
    },
    {
        "name": "Novartis AG",
        "ticker": "NOVN",
        "asset_class": AssetClass.EQUITY,
        "currency": "CHF",
        "exchange": "SIX",
        "country": "CH",
        "sector": "Healthcare",
        "industry": "Pharmaceuticals",
        "shares_outstanding": Decimal("2_040_000_000"),
        "listed_date": date(1996, 12, 20),
    },
    # --- South Korea ---
    {
        "name": "Samsung Electronics Co.",
        "ticker": "005930",
        "asset_class": AssetClass.EQUITY,
        "currency": "KRW",
        "exchange": "KRX",
        "country": "KR",
        "sector": "Technology",
        "industry": "Semiconductors",
        "shares_outstanding": Decimal("5_970_000_000"),
        "listed_date": date(1975, 6, 11),
    },
    # --- Australia ---
    {
        "name": "BHP Group Limited",
        "ticker": "BHP",
        "asset_class": AssetClass.EQUITY,
        "currency": "AUD",
        "exchange": "ASX",
        "country": "AU",
        "sector": "Materials",
        "industry": "Mining",
        "shares_outstanding": Decimal("5_060_000_000"),
        "listed_date": date(1885, 8, 13),
    },
    # --- Canada ---
    {
        "name": "Royal Bank of Canada",
        "ticker": "RY",
        "asset_class": AssetClass.EQUITY,
        "currency": "CAD",
        "exchange": "TSX",
        "country": "CA",
        "sector": "Financials",
        "industry": "Banking",
        "shares_outstanding": Decimal("1_410_000_000"),
        "listed_date": date(1869, 1, 1),
    },
    # --- Additional US ---
    {
        "name": "Meta Platforms Inc.",
        "ticker": "META",
        "asset_class": AssetClass.EQUITY,
        "currency": "USD",
        "exchange": "NASDAQ",
        "country": "US",
        "sector": "Technology",
        "industry": "Social Media",
        "shares_outstanding": Decimal("2_560_000_000"),
        "listed_date": date(2012, 5, 18),
    },
    {
        "name": "Berkshire Hathaway Inc.",
        "ticker": "BRK.B",
        "asset_class": AssetClass.EQUITY,
        "currency": "USD",
        "exchange": "NYSE",
        "country": "US",
        "sector": "Financials",
        "industry": "Diversified Holdings",
        "shares_outstanding": Decimal("2_170_000_000"),
        "listed_date": date(1996, 5, 9),
    },
    {
        "name": "Visa Inc.",
        "ticker": "V",
        "asset_class": AssetClass.EQUITY,
        "currency": "USD",
        "exchange": "NYSE",
        "country": "US",
        "sector": "Financials",
        "industry": "Payment Processing",
        "shares_outstanding": Decimal("2_050_000_000"),
        "listed_date": date(2008, 3, 19),
    },
    {
        "name": "Procter & Gamble Co.",
        "ticker": "PG",
        "asset_class": AssetClass.EQUITY,
        "currency": "USD",
        "exchange": "NYSE",
        "country": "US",
        "sector": "Consumer Staples",
        "industry": "Household Products",
        "shares_outstanding": Decimal("2_360_000_000"),
        "listed_date": date(1890, 1, 1),
    },
    {
        "name": "Chevron Corporation",
        "ticker": "CVX",
        "asset_class": AssetClass.EQUITY,
        "currency": "USD",
        "exchange": "NYSE",
        "country": "US",
        "sector": "Energy",
        "industry": "Oil & Gas",
        "shares_outstanding": Decimal("1_880_000_000"),
        "listed_date": date(1921, 6, 25),
    },
    {
        "name": "Pfizer Inc.",
        "ticker": "PFE",
        "asset_class": AssetClass.EQUITY,
        "currency": "USD",
        "exchange": "NYSE",
        "country": "US",
        "sector": "Healthcare",
        "industry": "Pharmaceuticals",
        "shares_outstanding": Decimal("5_640_000_000"),
        "listed_date": date(1944, 1, 1),
    },
    {
        "name": "Walt Disney Company",
        "ticker": "DIS",
        "asset_class": AssetClass.EQUITY,
        "currency": "USD",
        "exchange": "NYSE",
        "country": "US",
        "sector": "Consumer Discretionary",
        "industry": "Entertainment",
        "shares_outstanding": Decimal("1_830_000_000"),
        "listed_date": date(1957, 11, 12),
    },
    {
        "name": "Coca-Cola Company",
        "ticker": "KO",
        "asset_class": AssetClass.EQUITY,
        "currency": "USD",
        "exchange": "NYSE",
        "country": "US",
        "sector": "Consumer Staples",
        "industry": "Beverages",
        "shares_outstanding": Decimal("4_320_000_000"),
        "listed_date": date(1919, 9, 5),
    },
    # --- Additional Europe ---
    {
        "name": "ASML Holding NV",
        "ticker": "ASML",
        "asset_class": AssetClass.EQUITY,
        "currency": "EUR",
        "exchange": "EURONEXT",
        "country": "NL",
        "sector": "Technology",
        "industry": "Semiconductors",
        "shares_outstanding": Decimal("394_000_000"),
        "listed_date": date(1995, 3, 14),
    },
    {
        "name": "Novo Nordisk A/S",
        "ticker": "NOVO.B",
        "asset_class": AssetClass.EQUITY,
        "currency": "DKK",
        "exchange": "CPH",
        "country": "DK",
        "sector": "Healthcare",
        "industry": "Pharmaceuticals",
        "shares_outstanding": Decimal("4_480_000_000"),
        "listed_date": date(1981, 1, 1),
    },
    {
        "name": "Roche Holding AG",
        "ticker": "ROG",
        "asset_class": AssetClass.EQUITY,
        "currency": "CHF",
        "exchange": "SIX",
        "country": "CH",
        "sector": "Healthcare",
        "industry": "Pharmaceuticals",
        "shares_outstanding": Decimal("680_000_000"),
        "listed_date": date(1920, 4, 19),
    },
    # --- Additional UK ---
    {
        "name": "Rio Tinto PLC",
        "ticker": "RIO",
        "asset_class": AssetClass.EQUITY,
        "currency": "GBP",
        "exchange": "LSE",
        "country": "GB",
        "sector": "Materials",
        "industry": "Mining",
        "shares_outstanding": Decimal("1_630_000_000"),
        "listed_date": date(1962, 1, 1),
    },
    {
        "name": "BP PLC",
        "ticker": "BP",
        "asset_class": AssetClass.EQUITY,
        "currency": "GBP",
        "exchange": "LSE",
        "country": "GB",
        "sector": "Energy",
        "industry": "Oil & Gas",
        "shares_outstanding": Decimal("19_200_000_000"),
        "listed_date": date(1954, 1, 1),
    },
    # --- Additional Asia ---
    {
        "name": "Taiwan Semiconductor Manufacturing",
        "ticker": "2330",
        "asset_class": AssetClass.EQUITY,
        "currency": "TWD",
        "exchange": "TWSE",
        "country": "TW",
        "sector": "Technology",
        "industry": "Semiconductors",
        "shares_outstanding": Decimal("25_930_000_000"),
        "listed_date": date(1994, 9, 5),
    },
    {
        "name": "Alibaba Group Holding",
        "ticker": "9988",
        "asset_class": AssetClass.EQUITY,
        "currency": "HKD",
        "exchange": "HKEX",
        "country": "CN",
        "sector": "Technology",
        "industry": "E-Commerce",
        "shares_outstanding": Decimal("20_330_000_000"),
        "listed_date": date(2019, 11, 26),
    },
    # --- Additional Americas ---
    {
        "name": "Vale S.A.",
        "ticker": "VALE3",
        "asset_class": AssetClass.EQUITY,
        "currency": "BRL",
        "exchange": "B3",
        "country": "BR",
        "sector": "Materials",
        "industry": "Mining",
        "shares_outstanding": Decimal("4_390_000_000"),
        "listed_date": date(1942, 6, 1),
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


# ---------------------------------------------------------------------------
# Non-equity seed instruments (fixed income, options, futures, FX, swaps)
# ---------------------------------------------------------------------------

SEED_FIXED_INCOME: list[dict[str, object]] = [
    {
        "name": "US Treasury 10Y 4.5% 2034",
        "ticker": "UST10Y",
        "asset_class": AssetClass.FIXED_INCOME,
        "currency": "USD",
        "exchange": "OTC",
        "country": "US",
        "sector": "Government",
        "coupon_rate": Decimal("0.045000"),
        "coupon_frequency": 2,
        "maturity_date": date(2034, 6, 15),
        "issue_date": date(2024, 6, 15),
        "face_value": Decimal("1000.00"),
        "day_count_convention": "ACT/ACT",
        "credit_rating": "AAA",
        "issuer": "US Treasury",
        "seniority": "senior",
    },
    {
        "name": "UK Gilt 4.0% 2031",
        "ticker": "UKT4031",
        "asset_class": AssetClass.FIXED_INCOME,
        "currency": "GBP",
        "exchange": "LSE",
        "country": "GB",
        "sector": "Government",
        "coupon_rate": Decimal("0.040000"),
        "coupon_frequency": 2,
        "maturity_date": date(2031, 3, 7),
        "face_value": Decimal("100.00"),
        "day_count_convention": "ACT/ACT",
        "credit_rating": "AA",
        "issuer": "HM Treasury",
        "seniority": "senior",
    },
    {
        "name": "JPMorgan 5.25% 2030",
        "ticker": "JPM5030",
        "asset_class": AssetClass.FIXED_INCOME,
        "currency": "USD",
        "exchange": "OTC",
        "country": "US",
        "sector": "Financials",
        "coupon_rate": Decimal("0.052500"),
        "coupon_frequency": 2,
        "maturity_date": date(2030, 9, 15),
        "issue_date": date(2025, 9, 15),
        "face_value": Decimal("1000.00"),
        "day_count_convention": "30/360",
        "credit_rating": "A+",
        "issuer": "JPMorgan Chase & Co",
        "seniority": "senior",
        "callable": True,
    },
]

SEED_OPTIONS: list[dict[str, object]] = [
    {
        "name": "AAPL Dec 2026 200 Call",
        "ticker": "AAPL261220C200",
        "asset_class": AssetClass.OPTION,
        "currency": "USD",
        "exchange": "CBOE",
        "country": "US",
        "option_type": "CALL",
        "exercise_style": "american",
        "strike_price": Decimal("200.000000"),
        "expiry_date": date(2026, 12, 20),
        "contract_size": Decimal("100.0000"),
        "settlement_type": "physical",
    },
    {
        "name": "SPX Dec 2026 5500 Put",
        "ticker": "SPX261220P5500",
        "asset_class": AssetClass.OPTION,
        "currency": "USD",
        "exchange": "CBOE",
        "country": "US",
        "option_type": "PUT",
        "exercise_style": "european",
        "strike_price": Decimal("5500.000000"),
        "expiry_date": date(2026, 12, 20),
        "contract_size": Decimal("100.0000"),
        "settlement_type": "cash",
    },
]

SEED_FUTURES: list[dict[str, object]] = [
    {
        "name": "E-mini S&P 500 Sep 2026",
        "ticker": "ESU26",
        "asset_class": AssetClass.FUTURE,
        "currency": "USD",
        "exchange": "CME",
        "country": "US",
        "expiry_date": date(2026, 9, 18),
        "contract_size": Decimal("50.0000"),
        "tick_size": Decimal("0.25000000"),
        "tick_value": Decimal("12.5000"),
        "margin_initial": Decimal("15400.00"),
        "margin_maintenance": Decimal("14000.00"),
        "settlement_type": "cash",
        "last_trading_date": date(2026, 9, 18),
    },
    {
        "name": "Euro Bund Dec 2026",
        "ticker": "FGBLZ26",
        "asset_class": AssetClass.FUTURE,
        "currency": "EUR",
        "exchange": "EUREX",
        "country": "DE",
        "expiry_date": date(2026, 12, 8),
        "contract_size": Decimal("1000.0000"),
        "tick_size": Decimal("0.01000000"),
        "tick_value": Decimal("10.0000"),
        "margin_initial": Decimal("3200.00"),
        "margin_maintenance": Decimal("2800.00"),
        "settlement_type": "physical",
        "last_trading_date": date(2026, 12, 8),
        "first_notice_date": date(2026, 12, 1),
    },
]

SEED_FX: list[dict[str, object]] = [
    {
        "name": "EUR/USD Spot",
        "ticker": "EURUSD",
        "asset_class": AssetClass.FX,
        "currency": "USD",
        "exchange": "OTC",
        "country": "US",
        "base_currency": "EUR",
        "quote_currency": "USD",
        "pip_size": Decimal("0.00010000"),
        "lot_size": 100_000,
        "settlement_days": 2,
    },
    {
        "name": "GBP/USD Spot",
        "ticker": "GBPUSD",
        "asset_class": AssetClass.FX,
        "currency": "USD",
        "exchange": "OTC",
        "country": "US",
        "base_currency": "GBP",
        "quote_currency": "USD",
        "pip_size": Decimal("0.00010000"),
        "lot_size": 100_000,
        "settlement_days": 2,
    },
    {
        "name": "USD/JPY Spot",
        "ticker": "USDJPY",
        "asset_class": AssetClass.FX,
        "currency": "JPY",
        "exchange": "OTC",
        "country": "JP",
        "base_currency": "USD",
        "quote_currency": "JPY",
        "pip_size": Decimal("0.01000000"),
        "lot_size": 100_000,
        "settlement_days": 2,
    },
]

SEED_SWAPS: list[dict[str, object]] = [
    {
        "name": "USD 5Y SOFR IRS 3.5%",
        "ticker": "SOFR5Y3.5",
        "asset_class": AssetClass.SWAP,
        "currency": "USD",
        "exchange": "OTC",
        "country": "US",
        "swap_type": "interest_rate",
        "notional_currency": "USD",
        "fixed_rate": Decimal("0.035000"),
        "floating_index": "SOFR",
        "floating_spread": Decimal("0.000000"),
        "payment_frequency": "semi_annual",
        "day_count_convention": "ACT/360",
        "effective_date": date(2026, 1, 15),
        "maturity_date": date(2031, 1, 15),
    },
    {
        "name": "EUR 3Y EURIBOR IRS 2.8%",
        "ticker": "EURIBOR3Y2.8",
        "asset_class": AssetClass.SWAP,
        "currency": "EUR",
        "exchange": "OTC",
        "country": "DE",
        "swap_type": "interest_rate",
        "notional_currency": "EUR",
        "fixed_rate": Decimal("0.028000"),
        "floating_index": "EURIBOR",
        "floating_spread": Decimal("0.000000"),
        "payment_frequency": "quarterly",
        "day_count_convention": "30/360",
        "effective_date": date(2026, 3, 1),
        "maturity_date": date(2029, 3, 1),
    },
]

# Fields that belong on each extension type, not on the base instrument.
_FIXED_INCOME_FIELDS = {
    "coupon_rate", "coupon_frequency", "maturity_date", "issue_date",
    "face_value", "day_count_convention", "credit_rating", "issuer",
    "seniority", "callable", "putable",
}
_OPTION_FIELDS = {
    "underlying_id", "option_type", "exercise_style", "strike_price",
    "expiry_date", "contract_size", "settlement_type",
}
_FUTURE_FIELDS = {
    "underlying_id", "expiry_date", "contract_size", "tick_size", "tick_value",
    "margin_initial", "margin_maintenance", "settlement_type",
    "last_trading_date", "first_notice_date",
}
_FX_FIELDS = {"base_currency", "quote_currency", "pip_size", "lot_size", "settlement_days"}
_SWAP_FIELDS = {
    "swap_type", "notional_currency", "fixed_rate", "floating_index",
    "floating_spread", "payment_frequency", "day_count_convention",
    "effective_date", "maturity_date", "underlying_id",
}


def build_all_seed_records() -> dict[str, list]:
    """Return all seed records: instruments + all extension types.

    Returns a dict with keys: instruments, equity_extensions,
    fixed_income_extensions, option_extensions, future_extensions,
    fx_extensions, swap_extensions.
    """
    instruments, equity_ext = build_seed_records()

    fi_ext: list[FixedIncomeExtensionRecord] = []
    for data in SEED_FIXED_INCOME:
        instrument_id = str(uuid4())
        ext_data = {k: data[k] for k in _FIXED_INCOME_FIELDS if k in data}
        instr_data = {k: v for k, v in data.items() if k not in _FIXED_INCOME_FIELDS}
        instruments.append(InstrumentRecord(id=instrument_id, **instr_data))
        if ext_data:
            fi_ext.append(FixedIncomeExtensionRecord(instrument_id=instrument_id, **ext_data))

    opt_ext: list[OptionExtensionRecord] = []
    for data in SEED_OPTIONS:
        instrument_id = str(uuid4())
        ext_data = {k: data[k] for k in _OPTION_FIELDS if k in data}
        instr_data = {k: v for k, v in data.items() if k not in _OPTION_FIELDS}
        instruments.append(InstrumentRecord(id=instrument_id, **instr_data))
        if ext_data:
            opt_ext.append(OptionExtensionRecord(instrument_id=instrument_id, **ext_data))

    fut_ext: list[FutureExtensionRecord] = []
    for data in SEED_FUTURES:
        instrument_id = str(uuid4())
        ext_data = {k: data[k] for k in _FUTURE_FIELDS if k in data}
        instr_data = {k: v for k, v in data.items() if k not in _FUTURE_FIELDS}
        instruments.append(InstrumentRecord(id=instrument_id, **instr_data))
        if ext_data:
            fut_ext.append(FutureExtensionRecord(instrument_id=instrument_id, **ext_data))

    fx_ext: list[FXExtensionRecord] = []
    for data in SEED_FX:
        instrument_id = str(uuid4())
        ext_data = {k: data[k] for k in _FX_FIELDS if k in data}
        instr_data = {k: v for k, v in data.items() if k not in _FX_FIELDS}
        instruments.append(InstrumentRecord(id=instrument_id, **instr_data))
        if ext_data:
            fx_ext.append(FXExtensionRecord(instrument_id=instrument_id, **ext_data))

    swap_ext: list[SwapExtensionRecord] = []
    for data in SEED_SWAPS:
        instrument_id = str(uuid4())
        ext_data = {k: data[k] for k in _SWAP_FIELDS if k in data}
        instr_data = {k: v for k, v in data.items() if k not in _SWAP_FIELDS}
        instruments.append(InstrumentRecord(id=instrument_id, **instr_data))
        if ext_data:
            swap_ext.append(SwapExtensionRecord(instrument_id=instrument_id, **ext_data))

    return {
        "instruments": instruments,
        "equity_extensions": equity_ext,
        "fixed_income_extensions": fi_ext,
        "option_extensions": opt_ext,
        "future_extensions": fut_ext,
        "fx_extensions": fx_ext,
        "swap_extensions": swap_ext,
    }


def convert_external_instruments(
    externals: list[ExternalInstrument],
) -> tuple[list[InstrumentRecord], list[EquityExtensionRecord]]:
    """Convert adapter ExternalInstrument objects to ORM records."""
    instruments: list[InstrumentRecord] = []
    extensions: list[EquityExtensionRecord] = []
    for ext in externals:
        instrument_id = str(uuid4())
        instruments.append(
            InstrumentRecord(
                id=instrument_id,
                name=ext.name,
                ticker=ext.ticker,
                asset_class=ext.asset_class,
                currency=ext.currency,
                exchange=ext.exchange,
                country=ext.country,
                sector=ext.sector,
                industry=ext.industry,
                annual_drift=ext.annual_drift,
                annual_volatility=ext.annual_volatility,
                spread_bps=ext.spread_bps,
                is_active=ext.is_active,
            )
        )
    return instruments, extensions
