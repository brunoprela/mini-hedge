"""Compliance module wiring — repos, pre-trade gate, post-trade monitor, service."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.modules.platform.repositories import FundRepository
    from app.shared.database import TenantSessionFactory
    from app.shared.events import EventBus

from app.modules.cash_management.repositories.cash_balance import CashBalanceRepository
from app.modules.compliance.core.post_trade import PostTradeMonitor
from app.modules.compliance.core.pre_trade import PreTradeGate
from app.modules.compliance.repositories.rule import RuleRepository
from app.modules.compliance.repositories.violation import ViolationRepository
from app.modules.compliance.services import ComplianceService
from app.modules.positions.repositories import CurrentPositionRepository
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
    """Wire compliance module: repos, pre-trade gate, post-trade monitor, service.

    Compliance rules are NOT seeded on startup. They are created via the UI,
    API, or ``make seed``. When no rules exist for a fund, the pre-trade gate
    approves all trades (pass-through).
    """
    rule_repo = RuleRepository(sf)
    violation_repo = ViolationRepository(sf)
    cash_balance_repo = CashBalanceRepository(sf)
    position_service = app.state.position_service
    security_master = app.state.security_master_service

    pre_trade_gate = PreTradeGate(
        rule_repo=rule_repo,
        position_service=position_service,
        security_master=security_master,
        cash_balance_repo=cash_balance_repo,
    )

    audit_repo = app.state.audit_repo
    compliance_service = ComplianceService(
        rule_repo=rule_repo,
        violation_repo=violation_repo,
        pre_trade_gate=pre_trade_gate,
        audit_repo=audit_repo,
        position_service=position_service,
        security_master=security_master,
        event_bus=event_bus,
    )
    app.state.compliance_service = compliance_service

    # Post-trade monitor: subscribe to positions.changed for each fund
    position_repo = CurrentPositionRepository(sf)
    post_trade_monitor = PostTradeMonitor(
        session_factory=sf,
        rule_repo=rule_repo,
        violation_repo=violation_repo,
        position_repo=position_repo,
        security_master=security_master,
        event_bus=event_bus,
        cash_balance_repo=cash_balance_repo,
    )
    active_funds = await fund_repo.get_all_active()
    for fund in active_funds:
        topic = fund_topic(fund.slug, "positions.changed")
        event_bus.subscribe(topic, post_trade_monitor.handle_position_changed)
        pnl_topic = fund_topic(fund.slug, "pnl.updated")
        event_bus.subscribe(pnl_topic, post_trade_monitor.handle_mtm_update)
    logger.info("post_trade_monitor_subscribed", fund_count=len(active_funds))
