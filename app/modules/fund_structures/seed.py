"""Seed data for fund structures — master-feeder links, strategy books."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.modules.fund_structures.services import FundStructuresService
    from app.modules.platform.repositories import FundRepository
    from app.shared.database import TenantSessionFactory

logger = structlog.get_logger()


async def seed_dev_data(app: FastAPI, sf: TenantSessionFactory) -> None:
    """Idempotent dev-only seeding for fund structures."""
    svc: FundStructuresService = app.state.fund_structures_service
    fund_repo: FundRepository = app.state.fund_repo
    active_funds = await fund_repo.get_all_active()
    fund_slugs = {f.slug for f in active_funds}

    # --- Master-feeder: alpha is master, beta and gamma are feeders ---
    if "alpha" in fund_slugs and "beta" in fund_slugs and "gamma" in fund_slugs:
        try:
            existing = await svc.get_feeder_structure("alpha")
            if not existing:
                await svc.create_master_feeder_link(
                    "alpha", "beta", Decimal("0.40"),
                )
                await svc.create_master_feeder_link(
                    "alpha", "gamma", Decimal("0.25"),
                )
                logger.info("master_feeder_links_seeded", master="alpha", feeders=["beta", "gamma"])
        except Exception:
            logger.debug("master_feeder_seed_skipped", reason="already exists or error")

    # --- Strategy books for alpha fund ---
    if "alpha" in fund_slugs:
        async with sf.fund_scope("alpha"), sf() as session:
            existing_books = await svc.get_book_tree("alpha", session=session)
            if not existing_books:
                root = await svc.create_book(
                    "alpha", "Total Fund", "fund", session=session,
                )
                eq_book = await svc.create_book(
                    "alpha", "Equity Long/Short", "strategy",
                    parent_id=root.id, target_pct=Decimal("0.60"), session=session,
                )
                await svc.create_book(
                    "alpha", "Equity Long", "sub-strategy",
                    parent_id=eq_book.id, target_pct=Decimal("0.70"), session=session,
                )
                await svc.create_book(
                    "alpha", "Equity Short", "sub-strategy",
                    parent_id=eq_book.id, target_pct=Decimal("0.30"), session=session,
                )
                await svc.create_book(
                    "alpha", "Event Driven", "strategy",
                    parent_id=root.id, target_pct=Decimal("0.25"), session=session,
                )
                await svc.create_book(
                    "alpha", "Cash & Hedges", "strategy",
                    parent_id=root.id, target_pct=Decimal("0.15"), session=session,
                )
                logger.info("strategy_books_seeded", fund="alpha", books=6)

    logger.info("fund_structures_seed_complete")
