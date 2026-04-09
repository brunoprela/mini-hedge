"""Fund structures module wiring — master-feeder, strategy books, fund of funds."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.modules.fund_structures.repositories.fund_of_funds import FundOfFundsRepository
from app.modules.fund_structures.repositories.master_feeder import MasterFeederRepository
from app.modules.fund_structures.repositories.strategy_book import StrategyBookRepository
from app.modules.fund_structures.services import FundStructuresService

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.shared.database import TenantSessionFactory
    from app.shared.events import EventBus

logger = structlog.get_logger()


async def setup(
    app: FastAPI,
    sf: TenantSessionFactory,
    *,
    event_bus: EventBus | None = None,
    settings=None,
    **ctx,
) -> None:
    """Wire fund structures module (master-feeder, strategy books, fund of funds)."""
    mf_repo = MasterFeederRepository(sf)
    book_repo = StrategyBookRepository(sf)
    fof_repo = FundOfFundsRepository(sf)

    svc = FundStructuresService(
        master_feeder_repo=mf_repo,
        strategy_book_repo=book_repo,
        fof_repo=fof_repo,
        session_factory=sf,
        event_bus=event_bus,
    )
    app.state.fund_structures_service = svc
    logger.info("fund_structures_module_ready")
