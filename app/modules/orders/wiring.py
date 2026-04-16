"""Orders module wiring — repo, compliance gateway, broker, service, algo engine."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.modules.market_data.services import MarketDataService
    from app.modules.orders.core.broker_registry import BrokerRegistry
    from app.modules.platform.repositories import FundRepository
    from app.shared.adapters.broker import BrokerAdapter
    from app.shared.database import TenantSessionFactory
    from app.shared.events import BaseEvent, EventBus, EventHandler

from app.modules.orders.core.compliance_gateway import ComplianceGateway
from app.modules.orders.repositories import OrderFillRepository, OrderRepository
from app.modules.orders.services import OrderService

logger = structlog.get_logger()


async def setup(
    app: FastAPI,
    sf: TenantSessionFactory,
    *,
    event_bus: EventBus | None = None,
    settings=None,
    broker: BrokerAdapter | None = None,
    broker_registry: BrokerRegistry | None = None,
    fund_repo: FundRepository | None = None,
    **ctx,
) -> None:
    """Wire orders module: repo, compliance gateway, broker, service, algo engine."""
    from app.modules.orders.core.algo_engine import AlgoEngine
    from app.modules.orders.core.best_execution import BestExecutionService
    from app.modules.orders.core.routing_engine import RoutingEngine
    from app.modules.orders.repositories import (
        AllocationRepository,
        RoutingRepository,
        ScorecardRepository,
    )
    from app.modules.orders.services import AllocationService, ScorecardService

    order_repo = OrderRepository(sf)
    order_fill_repo = OrderFillRepository(sf)
    compliance_service = app.state.compliance_service
    compliance_gateway = ComplianceGateway(pre_trade_gate=compliance_service.pre_trade_gate)
    audit_repo = app.state.audit_repo
    market_data_service: MarketDataService = app.state.market_data_service

    # Multi-broker routing
    scorecard_repo = ScorecardRepository(sf)
    scorecard_service = ScorecardService(
        scorecard_repo=scorecard_repo,
        session_factory=sf,
    )

    routing_engine: RoutingEngine | None = None
    if broker_registry is not None and not broker_registry.is_single_broker:
        routing_repo = RoutingRepository(sf)
        routing_engine = RoutingEngine(
            broker_registry=broker_registry,
            scorecard_service=scorecard_service,
            routing_repo=routing_repo,
        )
        app.state.routing_repo = routing_repo

    order_service = OrderService(
        session_factory=sf,
        order_repo=order_repo,
        order_fill_repo=order_fill_repo,
        compliance_gateway=compliance_gateway,
        broker=broker,
        event_bus=event_bus,
        audit_repo=audit_repo,
        broker_registry=broker_registry,
        routing_engine=routing_engine,
        scorecard_service=scorecard_service,
        market_data_service=market_data_service,
    )

    # Wire algo engine (circular dep resolved via callback injection)
    algo_engine = AlgoEngine(order_repo=order_repo, session_factory=sf)
    algo_engine.set_submit_child(order_service.create_child_order)
    order_service._algo_engine = algo_engine

    app.state.order_repo = order_repo
    app.state.order_service = order_service
    app.state.algo_engine = algo_engine
    app.state.scorecard_service = scorecard_service
    if broker_registry is not None:
        app.state.broker_registry = broker_registry

    # Best execution service
    best_execution_service = BestExecutionService(
        routing_repo=RoutingRepository(sf),
        scorecard_service=scorecard_service,
    )
    app.state.best_execution_service = best_execution_service

    # Wire allocation service
    allocation_repo = AllocationRepository(sf)
    allocation_service = AllocationService(
        session_factory=sf,
        allocation_repo=allocation_repo,
        order_service=order_service,
        order_repo=order_repo,
        compliance_gateway=compliance_gateway,
        event_bus=event_bus,
    )
    app.state.allocation_service = allocation_service

    # Subscribe: auto-create orders from alpha engine order intents
    if event_bus is not None and fund_repo is not None:
        from app.modules.orders.interfaces import (
            CreateOrderRequest,
            OrderSide,
            OrderType,
            TimeInForce,
        )
        from app.shared.schema_registry import fund_topic

        active_funds = await fund_repo.get_all_active()
        for fund in active_funds:

            def _make_handler(slug: str) -> EventHandler:
                async def on_order_intents_generated(event: BaseEvent) -> None:
                    intents = event.data.get("intents", [])
                    portfolio_id_str = event.data.get("portfolio_id")
                    if not portfolio_id_str or not intents:
                        return
                    portfolio_id = UUID(portfolio_id_str)
                    async with sf.fund_scope(slug):
                        for intent in intents:
                            try:
                                request = CreateOrderRequest(
                                    portfolio_id=portfolio_id,
                                    instrument_id=intent["instrument_id"],
                                    side=OrderSide(intent["side"]),
                                    order_type=OrderType.MARKET,
                                    quantity=Decimal(str(intent["quantity"])),
                                    time_in_force=TimeInForce.DAY,
                                )
                                await order_service.create_order(
                                    request,
                                    fund_slug=slug,
                                    actor_id="alpha-engine",
                                )
                            except Exception:
                                logger.exception(
                                    "order_intent_create_failed",
                                    portfolio_id=portfolio_id_str,
                                    instrument_id=intent.get("instrument_id"),
                                )

                return on_order_intents_generated

            event_bus.subscribe(
                fund_topic(fund.slug, "order_intents.generated"),
                _make_handler(fund.slug),
            )
        logger.info(
            "orders_subscribed_to_order_intents",
            fund_count=len(active_funds),
        )
