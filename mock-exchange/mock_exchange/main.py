"""Mock Exchange — external market simulation service for mini-hedge."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

import structlog
from fastapi import FastAPI

from mock_exchange.config import settings
from mock_exchange.corporate_actions.engine import CorporateActionsEngine
from mock_exchange.corporate_actions.routes import router as corporate_actions_router
from mock_exchange.execution.brokers import DEFAULT_BROKERS
from mock_exchange.execution.engine import ExecutionEngine
from mock_exchange.execution.impact import MarketImpactModel
from mock_exchange.execution.routes import router as execution_router
from mock_exchange.fund_admin.routes import router as fund_admin_router
from mock_exchange.fund_admin.service import FundAdminService
from mock_exchange.market_data.routes import router as market_data_router
from mock_exchange.market_data.service import MarketDataService
from mock_exchange.reference_data.instruments import INSTRUMENT_UNIVERSE
from mock_exchange.reference_data.routes import router as reference_data_router
from mock_exchange.scenarios.engine import ScenarioEngine
from mock_exchange.scenarios.routes import router as scenarios_router
from mock_exchange.shared.kafka import MockExchangeProducer

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("mock_exchange_starting", simulator_enabled=settings.simulator_enabled)

    market_data_service = MarketDataService()
    app.state.market_data_service = market_data_service

    # Kafka producer for execution reports + price publishing
    producer = MockExchangeProducer(bootstrap_servers=settings.kafka_bootstrap_servers)

    # Build instrument lookup
    instruments = {i.ticker: i for i in INSTRUMENT_UNIVERSE}

    # Market impact model
    impact_model = MarketImpactModel(eta=settings.market_impact_eta)

    # Execution engine — wired with order books after simulator starts
    execution_engine = ExecutionEngine(
        producer=producer,
        market_data=market_data_service,
        impact_model=impact_model,
        instruments=instruments,
        brokers=dict(DEFAULT_BROKERS),
    )
    execution_engine.config.trading_hours_enabled = settings.trading_hours_enabled
    app.state.execution_engine = execution_engine

    # Corporate actions engine
    corporate_actions_engine = CorporateActionsEngine(producer=producer)
    app.state.corporate_actions_engine = corporate_actions_engine

    # Fund administrator simulation
    fund_admin_service = FundAdminService(execution_engine)
    app.state.fund_admin_service = fund_admin_service

    # Scenario engine for market regime control
    scenario_engine = ScenarioEngine(
        simulator=None,  # wired after simulator starts
        execution_engine=execution_engine,
    )
    app.state.scenario_engine = scenario_engine

    if settings.simulator_enabled:
        await market_data_service.start_simulator(
            interval_ms=settings.simulator_interval_ms,
            kafka_bootstrap_servers=settings.kafka_bootstrap_servers,
            schema_registry_url=settings.kafka_schema_registry_url,
            ambient_flow_enabled=settings.ambient_flow_enabled,
            ambient_flow_interval_ms=settings.ambient_flow_interval_ms,
        )
        scenario_engine.simulator = market_data_service.simulator

        # Wire order books and trade tape into execution engine
        execution_engine._order_books = market_data_service.order_books
        execution_engine._trade_tape = market_data_service.trade_tape

    logger.info("mock_exchange_started")
    yield

    if settings.simulator_enabled:
        market_data_service.stop_simulator()
    logger.info("mock_exchange_stopped")


app = FastAPI(
    title="Mock Exchange",
    description="External market simulation service for mini-hedge platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(market_data_router, prefix="/api/v1")
app.include_router(reference_data_router, prefix="/api/v1")
app.include_router(execution_router, prefix="/api/v1")
app.include_router(scenarios_router, prefix="/api/v1")
app.include_router(corporate_actions_router, prefix="/api/v1")
app.include_router(fund_admin_router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "mock-exchange"}
