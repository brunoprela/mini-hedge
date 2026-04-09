"""Orders module wiring — repo, compliance gateway, broker, service, algo engine, TCA."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.modules.market_data.service import MarketDataService
    from app.modules.orders.routing.broker_registry import BrokerRegistry
    from app.shared.adapters import BrokerAdapter
    from app.shared.database import TenantSessionFactory
    from app.shared.events import EventBus

from app.modules.orders.compliance_gateway import ComplianceGateway
from app.modules.orders.repository import OrderRepository
from app.modules.orders.service import OrderService

logger = structlog.get_logger()


async def setup(
    app: FastAPI,
    sf: TenantSessionFactory,
    *,
    event_bus: EventBus | None = None,
    settings=None,
    broker: BrokerAdapter | None = None,
    broker_registry: BrokerRegistry | None = None,
    **ctx,
) -> None:
    """Wire orders module: repo, compliance gateway, broker, service, algo engine, TCA."""
    from app.modules.orders.algo.engine import AlgoEngine
    from app.modules.orders.allocation.repository import AllocationRepository
    from app.modules.orders.allocation.service import AllocationService
    from app.modules.orders.best_execution import BestExecutionService
    from app.modules.orders.routing.engine import RoutingEngine
    from app.modules.orders.routing.repository import RoutingRepository
    from app.modules.orders.scorecard.repository import ScorecardRepository
    from app.modules.orders.scorecard.service import ScorecardService
    from app.modules.orders.tca.repository import TCARepository
    from app.modules.orders.tca.service import TCAService
    from app.modules.orders.tca.vwap import VWAPCalculator

    order_repo = OrderRepository(sf)
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

    # TCA
    tca_repo = TCARepository(sf)
    vwap_calculator = VWAPCalculator(market_data_service)
    tca_service = TCAService(
        tca_repo=tca_repo,
        order_repo=order_repo,
        vwap_calculator=vwap_calculator,
        scorecard_service=scorecard_service,
    )

    order_service = OrderService(
        session_factory=sf,
        order_repo=order_repo,
        compliance_gateway=compliance_gateway,
        broker=broker,
        event_bus=event_bus,
        audit_repo=audit_repo,
        broker_registry=broker_registry,
        routing_engine=routing_engine,
        scorecard_service=scorecard_service,
        market_data_service=market_data_service,
        tca_service=tca_service,
    )

    # Wire algo engine (circular dep resolved via callback injection)
    algo_engine = AlgoEngine(order_repo=order_repo)
    algo_engine.set_submit_child(order_service.create_child_order)
    order_service._algo_engine = algo_engine

    app.state.order_service = order_service
    app.state.algo_engine = algo_engine
    app.state.tca_service = tca_service
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
