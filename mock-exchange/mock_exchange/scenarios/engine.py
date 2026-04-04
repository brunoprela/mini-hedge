"""Scenario engine — controls market regime simulation.

Manages scenario state machine and applies regime parameters
to the GBM simulator and execution engine.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from mock_exchange.execution.engine import ExecutionEngine
    from mock_exchange.market_data.simulator import GBMSimulator

logger = structlog.get_logger()


class ScenarioState(StrEnum):
    IDLE = "idle"
    LOADED = "loaded"
    RUNNING = "running"


@dataclass
class RegimeParams:
    """Market regime parameters applied to the simulator."""

    drift_multiplier: float = 1.0
    volatility_multiplier: float = 1.0
    correlation_boost: float = 0.0


@dataclass
class ExecutionParams:
    """Execution behavior during a scenario."""

    fill_delay_ms: int = 50
    reject_rate: float = 0.0
    partial_fill_rate: float = 0.0
    slippage_bps: float = 2.0


@dataclass
class ScenarioPhase:
    """A single phase within a scenario."""

    name: str
    duration_seconds: float
    regime: RegimeParams
    execution: ExecutionParams | None = None


@dataclass
class ScenarioDefinition:
    """Complete scenario with one or more phases."""

    name: str
    description: str
    phases: list[ScenarioPhase]


# ---------------------------------------------------------------------------
#  Built-in presets
# ---------------------------------------------------------------------------

PRESETS: dict[str, ScenarioDefinition] = {
    "calm": ScenarioDefinition(
        name="calm",
        description="Normal market conditions — low volatility, moderate drift",
        phases=[
            ScenarioPhase(
                name="calm",
                duration_seconds=600,
                regime=RegimeParams(drift_multiplier=1.0, volatility_multiplier=1.0),
            ),
        ],
    ),
    "bull": ScenarioDefinition(
        name="bull",
        description="Bull market — high drift, low volatility",
        phases=[
            ScenarioPhase(
                name="rally",
                duration_seconds=600,
                regime=RegimeParams(drift_multiplier=2.5, volatility_multiplier=0.7),
            ),
        ],
    ),
    "bear": ScenarioDefinition(
        name="bear",
        description="Bear market — negative drift, elevated volatility",
        phases=[
            ScenarioPhase(
                name="selloff",
                duration_seconds=600,
                regime=RegimeParams(
                    drift_multiplier=-1.5,
                    volatility_multiplier=1.5,
                    correlation_boost=0.15,
                ),
                execution=ExecutionParams(fill_delay_ms=200, partial_fill_rate=0.1),
            ),
        ],
    ),
    "crash": ScenarioDefinition(
        name="crash",
        description="2008-style market crash — sharp selloff then slow recovery",
        phases=[
            ScenarioPhase(
                name="shock",
                duration_seconds=120,
                regime=RegimeParams(
                    drift_multiplier=-3.0,
                    volatility_multiplier=3.0,
                    correlation_boost=0.3,
                ),
                execution=ExecutionParams(
                    fill_delay_ms=5000,
                    reject_rate=0.15,
                    partial_fill_rate=0.3,
                    slippage_bps=20.0,
                ),
            ),
            ScenarioPhase(
                name="recovery",
                duration_seconds=300,
                regime=RegimeParams(
                    drift_multiplier=0.5,
                    volatility_multiplier=1.5,
                    correlation_boost=0.1,
                ),
                execution=ExecutionParams(fill_delay_ms=500, partial_fill_rate=0.1),
            ),
        ],
    ),
    "flash_crash": ScenarioDefinition(
        name="flash_crash",
        description="Flash crash — 10% drop in 20 seconds, rapid recovery",
        phases=[
            ScenarioPhase(
                name="crash",
                duration_seconds=20,
                regime=RegimeParams(
                    drift_multiplier=-10.0,
                    volatility_multiplier=5.0,
                    correlation_boost=0.4,
                ),
                execution=ExecutionParams(
                    fill_delay_ms=10000,
                    reject_rate=0.3,
                    slippage_bps=50.0,
                ),
            ),
            ScenarioPhase(
                name="recovery",
                duration_seconds=60,
                regime=RegimeParams(drift_multiplier=5.0, volatility_multiplier=2.0),
                execution=ExecutionParams(fill_delay_ms=200),
            ),
        ],
    ),
    "demo": ScenarioDefinition(
        name="demo",
        description="Demo-friendly — gentle bull market, looks good on dashboards",
        phases=[
            ScenarioPhase(
                name="steady_climb",
                duration_seconds=600,
                regime=RegimeParams(drift_multiplier=1.8, volatility_multiplier=0.5),
            ),
        ],
    ),
}


class ScenarioEngine:
    """Manages scenario lifecycle and applies parameters to simulator/execution."""

    def __init__(
        self,
        simulator: GBMSimulator | None = None,
        execution_engine: ExecutionEngine | None = None,
    ) -> None:
        self.simulator = simulator
        self.execution_engine = execution_engine
        self._state = ScenarioState.IDLE
        self._active_scenario: ScenarioDefinition | None = None
        self._current_phase: ScenarioPhase | None = None
        self._task: asyncio.Task | None = None  # type: ignore[type-arg]

    @property
    def state(self) -> ScenarioState:
        return self._state

    @property
    def active_scenario_name(self) -> str | None:
        return self._active_scenario.name if self._active_scenario else None

    @property
    def current_phase_name(self) -> str | None:
        return self._current_phase.name if self._current_phase else None

    def load_preset(self, name: str) -> ScenarioDefinition:
        if name not in PRESETS:
            msg = f"Unknown preset: {name!r}. Available: {sorted(PRESETS)}"
            raise ValueError(msg)
        scenario = PRESETS[name]
        self._active_scenario = scenario
        self._state = ScenarioState.LOADED
        logger.info("scenario_loaded", name=name, phases=len(scenario.phases))
        return scenario

    async def start(self) -> None:
        if self._active_scenario is None:
            msg = "No scenario loaded"
            raise ValueError(msg)
        self._state = ScenarioState.RUNNING
        self._task = asyncio.create_task(self._run_phases())

    async def _run_phases(self) -> None:
        if self._active_scenario is None:
            return
        for phase in self._active_scenario.phases:
            if self._state != ScenarioState.RUNNING:
                break
            self._current_phase = phase
            logger.info(
                "scenario_phase_started",
                scenario=self._active_scenario.name,
                phase=phase.name,
                duration=phase.duration_seconds,
            )
            self._apply_phase(phase)
            await asyncio.sleep(phase.duration_seconds)

        # All phases complete
        self._reset_params()
        self._state = ScenarioState.IDLE
        self._current_phase = None
        logger.info("scenario_completed", scenario=self._active_scenario.name)

    def _apply_phase(self, phase: ScenarioPhase) -> None:
        if self.simulator:
            self.simulator.apply_regime(
                drift_mult=phase.regime.drift_multiplier,
                vol_mult=phase.regime.volatility_multiplier,
                corr_boost=phase.regime.correlation_boost,
            )
        if self.execution_engine and phase.execution:
            self.execution_engine.update_config(
                fill_delay_ms=phase.execution.fill_delay_ms,
                reject_rate=phase.execution.reject_rate,
                partial_fill_rate=phase.execution.partial_fill_rate,
                slippage_bps=phase.execution.slippage_bps,
            )

    def _reset_params(self) -> None:
        if self.simulator:
            self.simulator.reset_regime()
        if self.execution_engine:
            self.execution_engine.update_config(
                fill_delay_ms=50,
                reject_rate=0.0,
                partial_fill_rate=0.0,
                slippage_bps=2.0,
            )

    def stop(self) -> None:
        self._state = ScenarioState.IDLE
        if self._task:
            self._task.cancel()
        self._reset_params()
        self._current_phase = None
        logger.info("scenario_stopped")

    def reset(self) -> None:
        self.stop()
        self._active_scenario = None
        logger.info("scenario_reset")
