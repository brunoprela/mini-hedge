"""Instrument reference data — the mock-exchange's view of the security universe.

This data mirrors what would come from DTCC, Bloomberg FIGI, or exchange feeds.
The platform fetches instruments from here via the ReferenceDataAdapter.

Drift, volatility, and spread parameters are sourced from the GBM simulator config
so the platform can use them for risk/attribution/alpha calculations.
"""

from __future__ import annotations

from mock_exchange.shared.models import InstrumentInfo

INSTRUMENT_UNIVERSE: list[InstrumentInfo] = [
    # --- US Technology ---
    InstrumentInfo(
        ticker="AAPL", name="Apple Inc.", asset_class="equity",
        currency="USD", exchange="NASDAQ", country="US",
        sector="Technology", industry="Consumer Electronics",
        annual_drift=0.12, annual_volatility=0.25, spread_bps=8.0,
    ),
    InstrumentInfo(
        ticker="MSFT", name="Microsoft Corporation", asset_class="equity",
        currency="USD", exchange="NASDAQ", country="US",
        sector="Technology", industry="Software",
        annual_drift=0.10, annual_volatility=0.22, spread_bps=6.0,
    ),
    InstrumentInfo(
        ticker="GOOGL", name="Alphabet Inc.", asset_class="equity",
        currency="USD", exchange="NASDAQ", country="US",
        sector="Technology", industry="Internet Services",
        annual_drift=0.08, annual_volatility=0.28, spread_bps=10.0,
    ),
    InstrumentInfo(
        ticker="NVDA", name="NVIDIA Corporation", asset_class="equity",
        currency="USD", exchange="NASDAQ", country="US",
        sector="Technology", industry="Semiconductors",
        annual_drift=0.15, annual_volatility=0.45, spread_bps=15.0,
    ),
    InstrumentInfo(
        ticker="META", name="Meta Platforms Inc.", asset_class="equity",
        currency="USD", exchange="NASDAQ", country="US",
        sector="Technology", industry="Social Media",
        annual_drift=0.11, annual_volatility=0.35, spread_bps=12.0,
    ),
    # --- US Consumer Discretionary ---
    InstrumentInfo(
        ticker="AMZN", name="Amazon.com Inc.", asset_class="equity",
        currency="USD", exchange="NASDAQ", country="US",
        sector="Consumer Discretionary", industry="E-Commerce",
        annual_drift=0.10, annual_volatility=0.30, spread_bps=10.0,
    ),
    InstrumentInfo(
        ticker="TSLA", name="Tesla Inc.", asset_class="equity",
        currency="USD", exchange="NASDAQ", country="US",
        sector="Consumer Discretionary", industry="Automobiles",
        annual_drift=0.05, annual_volatility=0.55, spread_bps=25.0,
    ),
    InstrumentInfo(
        ticker="DIS", name="Walt Disney Company", asset_class="equity",
        currency="USD", exchange="NYSE", country="US",
        sector="Consumer Discretionary", industry="Entertainment",
        annual_drift=0.04, annual_volatility=0.30, spread_bps=12.0,
    ),
    # --- US Financials ---
    InstrumentInfo(
        ticker="JPM", name="JPMorgan Chase & Co.", asset_class="equity",
        currency="USD", exchange="NYSE", country="US",
        sector="Financials", industry="Banking",
        annual_drift=0.08, annual_volatility=0.20, spread_bps=6.0,
    ),
    InstrumentInfo(
        ticker="GS", name="Goldman Sachs Group Inc.", asset_class="equity",
        currency="USD", exchange="NYSE", country="US",
        sector="Financials", industry="Investment Banking",
        annual_drift=0.07, annual_volatility=0.22, spread_bps=8.0,
    ),
    InstrumentInfo(
        ticker="BRK.B", name="Berkshire Hathaway Inc.", asset_class="equity",
        currency="USD", exchange="NYSE", country="US",
        sector="Financials", industry="Diversified Holdings",
        annual_drift=0.07, annual_volatility=0.15, spread_bps=5.0,
    ),
    InstrumentInfo(
        ticker="V", name="Visa Inc.", asset_class="equity",
        currency="USD", exchange="NYSE", country="US",
        sector="Financials", industry="Payment Processing",
        annual_drift=0.09, annual_volatility=0.20, spread_bps=6.0,
    ),
    # --- US Healthcare ---
    InstrumentInfo(
        ticker="JNJ", name="Johnson & Johnson", asset_class="equity",
        currency="USD", exchange="NYSE", country="US",
        sector="Healthcare", industry="Pharmaceuticals",
        annual_drift=0.05, annual_volatility=0.15, spread_bps=5.0,
    ),
    InstrumentInfo(
        ticker="UNH", name="UnitedHealth Group Inc.", asset_class="equity",
        currency="USD", exchange="NYSE", country="US",
        sector="Healthcare", industry="Managed Healthcare",
        annual_drift=0.09, annual_volatility=0.20, spread_bps=6.0,
    ),
    InstrumentInfo(
        ticker="PFE", name="Pfizer Inc.", asset_class="equity",
        currency="USD", exchange="NYSE", country="US",
        sector="Healthcare", industry="Pharmaceuticals",
        annual_drift=0.03, annual_volatility=0.25, spread_bps=10.0,
    ),
    # --- US Energy ---
    InstrumentInfo(
        ticker="XOM", name="Exxon Mobil Corporation", asset_class="equity",
        currency="USD", exchange="NYSE", country="US",
        sector="Energy", industry="Oil & Gas",
        annual_drift=0.06, annual_volatility=0.25, spread_bps=8.0,
    ),
    InstrumentInfo(
        ticker="CVX", name="Chevron Corporation", asset_class="equity",
        currency="USD", exchange="NYSE", country="US",
        sector="Energy", industry="Oil & Gas",
        annual_drift=0.06, annual_volatility=0.24, spread_bps=8.0,
    ),
    # --- US Consumer Staples ---
    InstrumentInfo(
        ticker="PG", name="Procter & Gamble Co.", asset_class="equity",
        currency="USD", exchange="NYSE", country="US",
        sector="Consumer Staples", industry="Household Products",
        annual_drift=0.04, annual_volatility=0.12, spread_bps=5.0,
    ),
    InstrumentInfo(
        ticker="KO", name="Coca-Cola Company", asset_class="equity",
        currency="USD", exchange="NYSE", country="US",
        sector="Consumer Staples", industry="Beverages",
        annual_drift=0.03, annual_volatility=0.14, spread_bps=5.0,
    ),
    # --- UK ---
    InstrumentInfo(
        ticker="AZN", name="AstraZeneca PLC", asset_class="equity",
        currency="GBP", exchange="LSE", country="GB",
        sector="Healthcare", industry="Pharmaceuticals",
        annual_drift=0.07, annual_volatility=0.20, spread_bps=8.0,
    ),
    InstrumentInfo(
        ticker="HSBA", name="HSBC Holdings PLC", asset_class="equity",
        currency="GBP", exchange="LSE", country="GB",
        sector="Financials", industry="Banking",
        annual_drift=0.04, annual_volatility=0.18, spread_bps=10.0,
    ),
    InstrumentInfo(
        ticker="SHEL", name="Shell PLC", asset_class="equity",
        currency="GBP", exchange="LSE", country="GB",
        sector="Energy", industry="Oil & Gas",
        annual_drift=0.05, annual_volatility=0.22, spread_bps=8.0,
    ),
    InstrumentInfo(
        ticker="ULVR", name="Unilever PLC", asset_class="equity",
        currency="GBP", exchange="LSE", country="GB",
        sector="Consumer Staples", industry="Personal Products",
        annual_drift=0.03, annual_volatility=0.15, spread_bps=6.0,
    ),
    InstrumentInfo(
        ticker="RIO", name="Rio Tinto PLC", asset_class="equity",
        currency="GBP", exchange="LSE", country="GB",
        sector="Materials", industry="Mining",
        annual_drift=0.05, annual_volatility=0.28, spread_bps=10.0,
    ),
    InstrumentInfo(
        ticker="BP", name="BP PLC", asset_class="equity",
        currency="GBP", exchange="LSE", country="GB",
        sector="Energy", industry="Oil & Gas",
        annual_drift=0.04, annual_volatility=0.24, spread_bps=10.0,
    ),
    # --- Germany ---
    InstrumentInfo(
        ticker="SAP", name="SAP SE", asset_class="equity",
        currency="EUR", exchange="XETRA", country="DE",
        sector="Technology", industry="Enterprise Software",
        annual_drift=0.10, annual_volatility=0.25, spread_bps=8.0,
    ),
    InstrumentInfo(
        ticker="SIE", name="Siemens AG", asset_class="equity",
        currency="EUR", exchange="XETRA", country="DE",
        sector="Industrials", industry="Industrial Conglomerates",
        annual_drift=0.06, annual_volatility=0.22, spread_bps=8.0,
    ),
    # --- France ---
    InstrumentInfo(
        ticker="MC", name="LVMH Moët Hennessy", asset_class="equity",
        currency="EUR", exchange="EURONEXT", country="FR",
        sector="Consumer Discretionary", industry="Luxury Goods",
        annual_drift=0.08, annual_volatility=0.28, spread_bps=10.0,
    ),
    InstrumentInfo(
        ticker="TTE", name="TotalEnergies SE", asset_class="equity",
        currency="EUR", exchange="EURONEXT", country="FR",
        sector="Energy", industry="Oil & Gas",
        annual_drift=0.05, annual_volatility=0.22, spread_bps=8.0,
    ),
    # --- Netherlands ---
    InstrumentInfo(
        ticker="ASML", name="ASML Holding NV", asset_class="equity",
        currency="EUR", exchange="EURONEXT", country="NL",
        sector="Technology", industry="Semiconductors",
        annual_drift=0.12, annual_volatility=0.35, spread_bps=10.0,
    ),
    # --- Denmark ---
    InstrumentInfo(
        ticker="NOVO.B", name="Novo Nordisk A/S", asset_class="equity",
        currency="DKK", exchange="CPH", country="DK",
        sector="Healthcare", industry="Pharmaceuticals",
        annual_drift=0.10, annual_volatility=0.28, spread_bps=8.0,
    ),
    # --- Japan ---
    InstrumentInfo(
        ticker="7203", name="Toyota Motor Corporation", asset_class="equity",
        currency="JPY", exchange="TSE", country="JP",
        sector="Consumer Discretionary", industry="Automobiles",
        annual_drift=0.04, annual_volatility=0.20, spread_bps=10.0,
    ),
    InstrumentInfo(
        ticker="6758", name="Sony Group Corporation", asset_class="equity",
        currency="JPY", exchange="TSE", country="JP",
        sector="Technology", industry="Consumer Electronics",
        annual_drift=0.06, annual_volatility=0.30, spread_bps=12.0,
    ),
    # --- Switzerland ---
    InstrumentInfo(
        ticker="NESN", name="Nestlé S.A.", asset_class="equity",
        currency="CHF", exchange="SIX", country="CH",
        sector="Consumer Staples", industry="Food Products",
        annual_drift=0.03, annual_volatility=0.12, spread_bps=5.0,
    ),
    InstrumentInfo(
        ticker="NOVN", name="Novartis AG", asset_class="equity",
        currency="CHF", exchange="SIX", country="CH",
        sector="Healthcare", industry="Pharmaceuticals",
        annual_drift=0.05, annual_volatility=0.18, spread_bps=6.0,
    ),
    InstrumentInfo(
        ticker="ROG", name="Roche Holding AG", asset_class="equity",
        currency="CHF", exchange="SIX", country="CH",
        sector="Healthcare", industry="Pharmaceuticals",
        annual_drift=0.04, annual_volatility=0.16, spread_bps=6.0,
    ),
    # --- South Korea ---
    InstrumentInfo(
        ticker="005930", name="Samsung Electronics Co.", asset_class="equity",
        currency="KRW", exchange="KRX", country="KR",
        sector="Technology", industry="Semiconductors",
        annual_drift=0.08, annual_volatility=0.30, spread_bps=15.0,
    ),
    # --- Taiwan ---
    InstrumentInfo(
        ticker="2330", name="Taiwan Semiconductor Manufacturing", asset_class="equity",
        currency="TWD", exchange="TWSE", country="TW",
        sector="Technology", industry="Semiconductors",
        annual_drift=0.10, annual_volatility=0.32, spread_bps=12.0,
    ),
    # --- China/HK ---
    InstrumentInfo(
        ticker="9988", name="Alibaba Group Holding", asset_class="equity",
        currency="HKD", exchange="HKEX", country="CN",
        sector="Technology", industry="E-Commerce",
        annual_drift=0.06, annual_volatility=0.40, spread_bps=18.0,
    ),
    # --- Australia ---
    InstrumentInfo(
        ticker="BHP", name="BHP Group Limited", asset_class="equity",
        currency="AUD", exchange="ASX", country="AU",
        sector="Materials", industry="Mining",
        annual_drift=0.06, annual_volatility=0.25, spread_bps=10.0,
    ),
    # --- Canada ---
    InstrumentInfo(
        ticker="RY", name="Royal Bank of Canada", asset_class="equity",
        currency="CAD", exchange="TSX", country="CA",
        sector="Financials", industry="Banking",
        annual_drift=0.05, annual_volatility=0.16, spread_bps=6.0,
    ),
    # --- Brazil ---
    InstrumentInfo(
        ticker="VALE3", name="Vale S.A.", asset_class="equity",
        currency="BRL", exchange="B3", country="BR",
        sector="Materials", industry="Mining",
        annual_drift=0.05, annual_volatility=0.35, spread_bps=15.0,
    ),
]

# Lookup by ticker for O(1) access
_INSTRUMENT_INDEX: dict[str, InstrumentInfo] = {i.ticker: i for i in INSTRUMENT_UNIVERSE}


def get_instrument(ticker: str) -> InstrumentInfo | None:
    return _INSTRUMENT_INDEX.get(ticker)


def get_all_instruments(
    asset_class: str | None = None,
    country: str | None = None,
    sector: str | None = None,
) -> list[InstrumentInfo]:
    result = INSTRUMENT_UNIVERSE
    if asset_class:
        result = [i for i in result if i.asset_class == asset_class]
    if country:
        result = [i for i in result if i.country == country]
    if sector:
        result = [i for i in result if i.sector == sector]
    return result
