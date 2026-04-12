"""Seed data for TCA — pre-computed TCA results for sample filled orders."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from app.modules.tca.models.tca_result import TCAResultRecord

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.shared.database import TenantSessionFactory

logger = structlog.get_logger()


async def seed_dev_data(app: FastAPI, sf: TenantSessionFactory) -> None:
    """Idempotent dev-only seeding — compute TCA for any filled orders missing results."""
    tca_service = getattr(app.state, "tca_service", None)
    if tca_service is None:
        logger.debug("tca_seed_skipped", reason="service not available")
        return

    order_repo = tca_service._order_repo
    tca_repo = tca_service._tca_repo

    # Find filled orders that don't yet have TCA results
    from sqlalchemy import select

    from app.modules.orders.models.order import OrderRecord

    async with order_repo._session(None) as session:
        stmt = select(OrderRecord).where(OrderRecord.state == "filled").limit(20)
        result = await session.execute(stmt)
        filled_orders = list(result.scalars().all())

    seeded = 0
    for order in filled_orders:
        existing = await tca_repo.get_by_order_id(order.id)
        if existing is not None:
            continue

        # Try computing TCA through the service (uses real VWAP + cost engine)
        try:
            from uuid import UUID

            report = await tca_service.compute_for_order(UUID(order.id))
            if report is not None:
                seeded += 1
        except Exception:
            logger.debug("tca_seed_order_skipped", order_id=order.id, reason="computation failed")

    if seeded:
        logger.info("tca_seed_complete", orders_computed=seeded)
    else:
        logger.debug("tca_seed_skipped", reason="no eligible orders or all already computed")
