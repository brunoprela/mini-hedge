"""Cash management module wiring — repos, service, event subscriptions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.modules.platform.repositories import FundRepository
    from app.shared.database import TenantSessionFactory
    from app.shared.events import EventBus

from app.modules.cash_management.repositories.cash_balance import CashBalanceRepository
from app.modules.cash_management.repositories.cash_journal import CashJournalRepository
from app.modules.cash_management.repositories.cash_projection import CashProjectionRepository
from app.modules.cash_management.repositories.scheduled_flow import ScheduledFlowRepository
from app.modules.cash_management.repositories.settlement import SettlementRepository
from app.modules.cash_management.services import CashManagementService
from app.shared.schema_registry import fund_topic

logger = structlog.get_logger()


async def setup(
    app: FastAPI,
    sf: TenantSessionFactory,
    *,
    event_bus: EventBus | None = None,
    settings=None,
    fund_repo: FundRepository | None = None,
    **ctx,
) -> None:
    """Wire cash management module: repos, service, event subscriptions."""
    sm_service = app.state.security_master_service
    cash_service = CashManagementService(
        session_factory=sf,
        balance_repo=CashBalanceRepository(sf),
        journal_repo=CashJournalRepository(sf),
        settlement_repo=SettlementRepository(sf),
        scheduled_flow_repo=ScheduledFlowRepository(sf),
        projection_repo=CashProjectionRepository(sf),
        security_master_service=sm_service,
        event_bus=event_bus,
    )
    app.state.cash_service = cash_service

    # Subscribe to trades.executed for automatic settlement creation
    active_funds = await fund_repo.get_all_active()
    for fund in active_funds:
        topic = fund_topic(fund.slug, "trades.executed")
        event_bus.subscribe(topic, cash_service.handle_trade_executed)
    logger.info("cash_management_subscribed", fund_count=len(active_funds))
