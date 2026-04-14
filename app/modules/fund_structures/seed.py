"""Seed data for fund structures — master-feeder links, strategy books.

All queries and inserts use a single session per block to avoid connection
pool churn through PgBouncer during startup.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.shared.database import TenantSessionFactory

logger = structlog.get_logger()


async def seed_dev_data(app: FastAPI, sf: TenantSessionFactory) -> None:
    """Idempotent dev-only seeding for fund structures."""
    from app.modules.fund_structures.models.master_feeder_link import MasterFeederLinkRecord
    from app.modules.fund_structures.models.strategy_book import StrategyBookRecord
    from app.modules.platform.repositories import FundRepository

    fund_repo: FundRepository = app.state.fund_repo
    active_funds = await fund_repo.get_all_active()
    fund_slugs = {f.slug for f in active_funds}

    # --- Master-feeder: alpha is master, beta and gamma are feeders ---
    if "alpha" in fund_slugs and "beta" in fund_slugs and "gamma" in fund_slugs:
        try:
            async with sf.fund_scope("alpha"):
                async with sf() as session:
                    existing = (
                        await session.execute(
                            select(MasterFeederLinkRecord).where(
                                MasterFeederLinkRecord.master_fund_slug == "alpha"
                            )
                        )
                    ).scalars().first()
                    if not existing:
                        session.add_all([
                            MasterFeederLinkRecord(
                                master_fund_slug="alpha",
                                feeder_fund_slug="beta",
                                allocation_pct=Decimal("0.40"),
                            ),
                            MasterFeederLinkRecord(
                                master_fund_slug="alpha",
                                feeder_fund_slug="gamma",
                                allocation_pct=Decimal("0.25"),
                            ),
                        ])
                        await session.commit()
                        logger.info("master_feeder_links_seeded", master="alpha", feeders=["beta", "gamma"])
        except IntegrityError:
            logger.debug("master_feeder_seed_skipped", reason="already exists")

    # --- Strategy books for alpha fund ---
    if "alpha" in fund_slugs:
        try:
            async with sf.fund_scope("alpha"):
                async with sf() as session:
                    existing_book = (
                        await session.execute(
                            select(StrategyBookRecord).where(
                                StrategyBookRecord.fund_slug == "alpha"
                            )
                        )
                    ).scalars().first()
                    if not existing_book:
                        root = StrategyBookRecord(
                            fund_slug="alpha", name="Total Fund",
                            level="fund", target_allocation_pct=Decimal("1.0"),
                        )
                        session.add(root)
                        await session.flush()

                        eq_book = StrategyBookRecord(
                            fund_slug="alpha", name="Equity Long/Short",
                            level="strategy", parent_id=root.id,
                            target_allocation_pct=Decimal("0.60"),
                        )
                        session.add(eq_book)
                        await session.flush()

                        session.add_all([
                            StrategyBookRecord(
                                fund_slug="alpha", name="Equity Long",
                                level="sub-strategy", parent_id=eq_book.id,
                                target_allocation_pct=Decimal("0.70"),
                            ),
                            StrategyBookRecord(
                                fund_slug="alpha", name="Equity Short",
                                level="sub-strategy", parent_id=eq_book.id,
                                target_allocation_pct=Decimal("0.30"),
                            ),
                            StrategyBookRecord(
                                fund_slug="alpha", name="Event Driven",
                                level="strategy", parent_id=root.id,
                                target_allocation_pct=Decimal("0.25"),
                            ),
                            StrategyBookRecord(
                                fund_slug="alpha", name="Cash & Hedges",
                                level="strategy", parent_id=root.id,
                                target_allocation_pct=Decimal("0.15"),
                            ),
                        ])
                        await session.commit()
                        logger.info("strategy_books_seeded", fund="alpha", books=6)
        except IntegrityError:
            logger.debug("strategy_books_seed_skipped", reason="already exists")

    logger.info("fund_structures_seed_complete")
