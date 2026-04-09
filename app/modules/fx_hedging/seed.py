"""Seed data for FX hedging -- interest rates and sample forwards."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from app.modules.platform.seed import (
    PORTFOLIO_ALPHA_EQUITY_LS_ID,
    PORTFOLIO_ALPHA_GLOBAL_MACRO_ID,
    PORTFOLIO_BETA_STAT_ARB_ID,
)

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.modules.platform.repositories import FundRepository
    from app.shared.database import TenantSessionFactory

logger = structlog.get_logger()


async def seed_dev_data(app: FastAPI, sf: TenantSessionFactory) -> None:
    """Idempotent dev-only seeding for FX hedging."""
    from app.modules.fx_hedging.models.fx_forward import FXForwardRecord
    from app.modules.fx_hedging.models.fx_interest_rate import FXInterestRateRecord
    from app.modules.fx_hedging.repositories import (
        FXForwardRepository,
        FXInterestRateRepository,
    )

    forward_repo = FXForwardRepository(sf)
    rate_repo = FXInterestRateRepository(sf)

    fund_repo: FundRepository = app.state.fund_repo
    active_funds = await fund_repo.get_all_active()

    # Seed interest rates for major currencies
    seed_rates = [
        ("USD", Decimal("0.0530"), 360),
        ("EUR", Decimal("0.0375"), 360),
        ("GBP", Decimal("0.0525"), 360),
        ("JPY", Decimal("0.0010"), 360),
        ("CHF", Decimal("0.0175"), 360),
        ("AUD", Decimal("0.0435"), 360),
        ("CAD", Decimal("0.0500"), 360),
    ]

    for fund in active_funds:
        async with sf.fund_scope(fund.slug), sf() as session:
            existing_rates = await rate_repo.get_all(session=session)
            if not existing_rates:
                for ccy, rate, tenor in seed_rates:
                    await rate_repo.upsert(
                        FXInterestRateRecord(
                            currency=ccy,
                            rate=rate,
                            tenor_days=tenor,
                            source="seed",
                        ),
                        session=session,
                    )
                logger.info("fx_rates_seeded", fund=fund.slug, count=len(seed_rates))

    # Seed sample FX forwards for the alpha fund
    # These portfolios hold non-USD positions (GBP, EUR, JPY, CHF)
    today = date.today()
    seed_forwards = [
        # Alpha Equity L/S -- hedge GBP and EUR exposure
        (
            PORTFOLIO_ALPHA_EQUITY_LS_ID,
            "USD",
            "GBP",
            "sell",
            Decimal("5000000"),
            Decimal("1.2650"),
            Decimal("1.2700"),
            today - timedelta(days=15),
            today + timedelta(days=15),
        ),
        (
            PORTFOLIO_ALPHA_EQUITY_LS_ID,
            "USD",
            "EUR",
            "sell",
            Decimal("3000000"),
            Decimal("1.0820"),
            Decimal("1.0850"),
            today - timedelta(days=10),
            today + timedelta(days=20),
        ),
        # Alpha Global Macro -- hedge JPY and CHF
        (
            PORTFOLIO_ALPHA_GLOBAL_MACRO_ID,
            "USD",
            "JPY",
            "sell",
            Decimal("400000000"),
            Decimal("0.006700"),
            Decimal("0.006720"),
            today - timedelta(days=20),
            today + timedelta(days=40),
        ),
        (
            PORTFOLIO_ALPHA_GLOBAL_MACRO_ID,
            "USD",
            "CHF",
            "sell",
            Decimal("2000000"),
            Decimal("1.1350"),
            Decimal("1.1380"),
            today - timedelta(days=5),
            today + timedelta(days=25),
        ),
        # Beta Stat Arb -- hedge EUR exposure
        (
            PORTFOLIO_BETA_STAT_ARB_ID,
            "USD",
            "EUR",
            "sell",
            Decimal("4000000"),
            Decimal("1.0810"),
            Decimal("1.0840"),
            today - timedelta(days=12),
            today + timedelta(days=18),
        ),
    ]

    for fund in active_funds:
        if fund.slug != "alpha" and fund.slug != "beta":
            continue
        async with sf.fund_scope(fund.slug), sf() as session:
            existing_fwds = await forward_repo.get_by_portfolio(
                UUID(PORTFOLIO_ALPHA_EQUITY_LS_ID),
                session=session,
            )
            if existing_fwds:
                continue
            for (
                pid,
                base,
                quote,
                direction,
                notional,
                rate,
                spot,
                trade_dt,
                maturity_dt,
            ) in seed_forwards:
                # Only seed forwards that belong to this fund's portfolios
                portfolio_ids_for_fund = {
                    "alpha": {PORTFOLIO_ALPHA_EQUITY_LS_ID, PORTFOLIO_ALPHA_GLOBAL_MACRO_ID},
                    "beta": {PORTFOLIO_BETA_STAT_ARB_ID},
                }
                if pid not in portfolio_ids_for_fund.get(fund.slug, set()):
                    continue
                await forward_repo.create(
                    FXForwardRecord(
                        portfolio_id=pid,
                        base_currency=base,
                        quote_currency=quote,
                        direction=direction,
                        notional=notional,
                        contract_rate=rate,
                        spot_at_inception=spot,
                        trade_date=trade_dt,
                        maturity_date=maturity_dt,
                        status="open",
                        counterparty="MOCK-BANK-1",
                    ),
                    session=session,
                )
            logger.info("fx_forwards_seeded", fund=fund.slug)
