"""Root conftest — FakeProducer spy, shared fixtures, test app."""

from __future__ import annotations

import random
from typing import Any

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from mock_exchange.execution.engine import ExecutionEngine
from mock_exchange.execution.routes import router as execution_router
from mock_exchange.market_data.routes import router as market_data_router
from mock_exchange.market_data.service import MarketDataService
from mock_exchange.market_data.simulator import GBMSimulator
from mock_exchange.reference_data.routes import router as reference_data_router
from mock_exchange.scenarios.engine import ScenarioEngine
from mock_exchange.scenarios.routes import router as scenarios_router

from .factories import make_small_universe

# ---------------------------------------------------------------------------
# FakeProducer — spy replacement for MockExchangeProducer
# ---------------------------------------------------------------------------


class FakeProducer:
    """Records produce() calls instead of sending to Kafka."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    def produce(self, topic: str, event_type: str, data: dict[str, Any]) -> None:
        self.messages.append({"topic": topic, "event_type": event_type, "data": data})

    def flush(self, timeout: float = 1.0) -> None:
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_producer() -> FakeProducer:
    return FakeProducer()


@pytest.fixture
def execution_engine(fake_producer: FakeProducer) -> ExecutionEngine:
    return ExecutionEngine(producer=fake_producer, market_data=None)  # type: ignore[arg-type]


@pytest.fixture
def seeded_execution_engine(fake_producer: FakeProducer) -> ExecutionEngine:
    random.seed(42)
    return ExecutionEngine(producer=fake_producer, market_data=None)  # type: ignore[arg-type]


@pytest.fixture
def gbm_simulator(fake_producer: FakeProducer) -> GBMSimulator:
    np.random.seed(42)
    return GBMSimulator(
        producer=fake_producer,  # type: ignore[arg-type]
        universe=make_small_universe(),
        interval_ms=100,
    )


@pytest.fixture
def market_data_service() -> MarketDataService:
    return MarketDataService()


# ---------------------------------------------------------------------------
# Integration test app — bypasses real lifespan (no Kafka)
# ---------------------------------------------------------------------------


@pytest.fixture
async def test_app(fake_producer: FakeProducer) -> AsyncClient:
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(market_data_router, prefix="/api/v1")
    app.include_router(reference_data_router, prefix="/api/v1")
    app.include_router(execution_router, prefix="/api/v1")
    app.include_router(scenarios_router, prefix="/api/v1")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "mock-exchange"}

    # Wire services with fakes
    from mock_exchange.market_data.simulator import DEFAULT_UNIVERSE

    mds = MarketDataService()
    mds._simulator = GBMSimulator(
        producer=fake_producer,  # type: ignore[arg-type]
        universe=list(DEFAULT_UNIVERSE),
    )
    app.state.market_data_service = mds
    app.state.execution_engine = ExecutionEngine(
        producer=fake_producer,  # type: ignore[arg-type]
        market_data=mds,
    )
    app.state.scenario_engine = ScenarioEngine(
        simulator=mds._simulator,
        execution_engine=app.state.execution_engine,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client  # type: ignore[misc]
