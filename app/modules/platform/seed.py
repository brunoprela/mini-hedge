"""Seed data for platform — default fund and portfolios."""

from app.modules.platform.models import FundRecord, PortfolioRecord

# Fixed UUIDs for reproducible local development
DEFAULT_FUND_ID = "10000000-0000-0000-0000-000000000001"
PORTFOLIO_EQUITY_LS_ID = "20000000-0000-0000-0000-000000000001"
PORTFOLIO_GLOBAL_MACRO_ID = "20000000-0000-0000-0000-000000000002"


def build_seed_fund() -> FundRecord:
    return FundRecord(
        id=DEFAULT_FUND_ID,
        slug="fund-alpha",
        name="Alpha Capital Partners",
        status="active",
        base_currency="USD",
    )


def build_seed_portfolios() -> list[PortfolioRecord]:
    return [
        PortfolioRecord(
            id=PORTFOLIO_EQUITY_LS_ID,
            fund_id=DEFAULT_FUND_ID,
            slug="equity-long-short",
            name="Equity Long/Short",
            strategy="equity_long_short",
        ),
        PortfolioRecord(
            id=PORTFOLIO_GLOBAL_MACRO_ID,
            fund_id=DEFAULT_FUND_ID,
            slug="global-macro",
            name="Global Macro",
            strategy="global_macro",
        ),
    ]
