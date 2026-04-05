"""Seed script — provisions portfolios, compliance rules, and cash balances.

Run with: uv run python -m app.seed

Funds, users, operators, and API keys are seeded on app startup (setup.py).
This script seeds business data that should NOT auto-create on every restart:
  - Portfolios (per fund)
  - Compliance rules (per fund)
  - Initial cash balances (subscription capital per portfolio)

Idempotent: skips if data already exists.
"""

import asyncio
from decimal import Decimal

import structlog

from app.config import get_settings
from app.modules.cash_management.models import CashBalanceRecord
from app.modules.cash_management.repository import CashBalanceRepository
from app.modules.compliance.repository import RuleRepository
from app.modules.compliance.seed import build_seed_compliance_rules
from app.modules.platform.fund_repository import FundRepository
from app.modules.platform.portfolio_repository import PortfolioRepository
from app.modules.platform.seed import build_seed_portfolios
from app.modules.security_master.repository import InstrumentRepository
from app.modules.security_master.seed import build_seed_records
from app.shared.database import build_engine
from app.shared.logging import setup_logging

logger = structlog.get_logger()

# Initial subscription capital per portfolio (USD).
# Represents the cash a fund allocates to each strategy book on day one.
_INITIAL_CASH: dict[str, Decimal] = {
    "20000000-0000-0000-0000-000000000001": Decimal("50_000_000"),  # Alpha Equity L/S
    "20000000-0000-0000-0000-000000000002": Decimal("30_000_000"),  # Alpha Global Macro
    "20000000-0000-0000-0000-000000000010": Decimal("40_000_000"),  # Beta Stat Arb
    "20000000-0000-0000-0000-000000000011": Decimal("25_000_000"),  # Beta Momentum
    "20000000-0000-0000-0000-000000000012": Decimal("35_000_000"),  # Beta Market Neutral
    "20000000-0000-0000-0000-000000000020": Decimal("45_000_000"),  # Gamma Event-Driven
    "20000000-0000-0000-0000-000000000021": Decimal("20_000_000"),  # Gamma Distressed
}


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    _, session_factory = build_engine()

    fund_repo = FundRepository(session_factory)
    portfolio_repo = PortfolioRepository(session_factory)

    # ── Instruments ──────────────────────────────────────────────────
    instrument_repo = InstrumentRepository(session_factory)
    existing_instruments = await instrument_repo.get_all_active()
    if existing_instruments:
        print(f"  Instruments: {len(existing_instruments)} already exist, skipping.")
    else:
        instruments, extensions = build_seed_records()
        await instrument_repo.insert_batch(instruments, extensions)
        print(f"  Instruments: seeded {len(instruments)} instruments.")

    # ── Portfolios ───────────────────────────────────────────────────
    funds = await fund_repo.get_all_active()
    if not funds:
        print("  No funds found. Start the app first (`make up`) to seed funds.")
        return

    existing_portfolios = await portfolio_repo.get_by_fund(str(funds[0].id))
    if existing_portfolios:
        print("  Portfolios: already exist, skipping.")
    else:
        portfolios = build_seed_portfolios()
        await portfolio_repo.insert_batch(portfolios)
        print(f"  Portfolios: seeded {len(portfolios)} across {len(funds)} funds.")

    # ── Compliance rules ─────────────────────────────────────────────
    rule_repo = RuleRepository(session_factory)
    for fund in funds:
        async with session_factory.fund_scope(fund.slug):
            existing_rules = await rule_repo.get_all()
            if existing_rules:
                print(
                    f"  Compliance rules ({fund.slug}): "
                    f"{len(existing_rules)} already exist, skipping."
                )
                continue
            rules = build_seed_compliance_rules(fund.slug)
            for rule in rules:
                await rule_repo.insert(rule)
            print(f"  Compliance rules ({fund.slug}): seeded {len(rules)} rules.")

    # ── Initial cash balances ──────────────────────────────────────────
    cash_repo = CashBalanceRepository(session_factory)
    all_portfolios = build_seed_portfolios()
    # Group portfolios by fund for fund_scope
    fund_id_to_slug = {f.id: f.slug for f in funds}
    cash_seeded = 0
    for portfolio in all_portfolios:
        fund_slug = fund_id_to_slug.get(portfolio.fund_id)
        if fund_slug is None:
            continue
        initial_amount = _INITIAL_CASH.get(portfolio.id, Decimal("10_000_000"))
        async with session_factory.fund_scope(fund_slug):
            existing = await cash_repo.get_by_portfolio_currency(
                __import__("uuid").UUID(portfolio.id), "USD"
            )
            if existing is not None:
                continue
            record = CashBalanceRecord(
                portfolio_id=portfolio.id,
                currency="USD",
                available_balance=initial_amount,
                pending_inflows=Decimal(0),
                pending_outflows=Decimal(0),
            )
            await cash_repo.upsert(record)
            cash_seeded += 1
    if cash_seeded:
        print(f"  Cash balances: seeded {cash_seeded} portfolios with initial capital.")
    else:
        print("  Cash balances: already exist, skipping.")

    print("\nDone. Run `uv run python -m app.seed_trades` to seed trades.")


if __name__ == "__main__":
    asyncio.run(main())
