"""Tests for ScenarioEngine — state machine transitions, phase application."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from mock_exchange.scenarios.engine import (
    PRESETS,
    RegimeParams,
    ScenarioDefinition,
    ScenarioEngine,
    ScenarioPhase,
    ScenarioState,
)


@pytest.fixture
def mock_simulator() -> MagicMock:
    sim = MagicMock()
    sim.apply_regime = MagicMock()
    sim.reset_regime = MagicMock()
    return sim


@pytest.fixture
def mock_execution_engine() -> MagicMock:
    eng = MagicMock()
    eng.update_config = MagicMock()
    return eng


@pytest.fixture
def engine(
    mock_simulator: MagicMock,
    mock_execution_engine: MagicMock,
) -> ScenarioEngine:
    return ScenarioEngine(
        simulator=mock_simulator,
        execution_engine=mock_execution_engine,
    )


class TestStateTransitions:
    def test_initial_state_is_idle(self, engine: ScenarioEngine) -> None:
        assert engine.state == ScenarioState.IDLE

    def test_load_transitions_to_loaded(self, engine: ScenarioEngine) -> None:
        engine.load_preset("calm")
        assert engine.state == ScenarioState.LOADED
        assert engine.active_scenario_name == "calm"

    def test_load_unknown_raises(self, engine: ScenarioEngine) -> None:
        with pytest.raises(ValueError, match="Unknown preset"):
            engine.load_preset("nonexistent")

    def test_all_presets_loadable(self) -> None:
        for name in PRESETS:
            eng = ScenarioEngine()
            result = eng.load_preset(name)
            assert isinstance(result, ScenarioDefinition)
            assert result.name == name

    async def test_start_transitions_to_running(
        self, engine: ScenarioEngine,
    ) -> None:
        engine.load_preset("calm")
        await engine.start()
        assert engine.state == ScenarioState.RUNNING

    async def test_start_without_load_raises(self) -> None:
        eng = ScenarioEngine()
        with pytest.raises(ValueError, match="No scenario loaded"):
            await eng.start()

    def test_stop_transitions_to_idle(self, engine: ScenarioEngine) -> None:
        engine.load_preset("calm")
        engine.stop()
        assert engine.state == ScenarioState.IDLE

    def test_reset_clears_scenario(self, engine: ScenarioEngine) -> None:
        engine.load_preset("calm")
        engine.reset()
        assert engine.state == ScenarioState.IDLE
        assert engine.active_scenario_name is None


class TestPhaseApplication:
    async def test_applies_regime_to_simulator(
        self,
        engine: ScenarioEngine,
        mock_simulator: MagicMock,
    ) -> None:
        engine.load_preset("bear")
        await engine.start()
        await asyncio.sleep(0.05)
        mock_simulator.apply_regime.assert_called_once_with(
            drift_mult=-1.5,
            vol_mult=1.5,
            corr_boost=0.15,
        )
        engine.stop()

    async def test_applies_execution_params(
        self,
        engine: ScenarioEngine,
        mock_execution_engine: MagicMock,
    ) -> None:
        engine.load_preset("bear")
        await engine.start()
        await asyncio.sleep(0.05)
        mock_execution_engine.update_config.assert_any_call(
            fill_delay_ms=200,
            reject_rate=0.0,
            partial_fill_rate=0.1,
            slippage_bps=2.0,
        )
        engine.stop()

    async def test_stop_resets_simulator(
        self,
        engine: ScenarioEngine,
        mock_simulator: MagicMock,
    ) -> None:
        engine.load_preset("calm")
        await engine.start()
        engine.stop()
        mock_simulator.reset_regime.assert_called_once()

    async def test_stop_resets_execution_config(
        self,
        engine: ScenarioEngine,
        mock_execution_engine: MagicMock,
    ) -> None:
        engine.load_preset("calm")
        await engine.start()
        engine.stop()
        mock_execution_engine.update_config.assert_called_with(
            fill_delay_ms=50,
            reject_rate=0.0,
            partial_fill_rate=0.0,
            slippage_bps=2.0,
        )

    async def test_phases_complete_to_idle(self) -> None:
        """Custom short-duration scenario completes and returns to idle."""
        scenario = ScenarioDefinition(
            name="test",
            description="test scenario",
            phases=[
                ScenarioPhase(
                    name="phase1",
                    duration_seconds=0.01,
                    regime=RegimeParams(),
                ),
                ScenarioPhase(
                    name="phase2",
                    duration_seconds=0.01,
                    regime=RegimeParams(),
                ),
            ],
        )
        eng = ScenarioEngine()
        eng._active_scenario = scenario
        eng._state = ScenarioState.LOADED
        await eng.start()
        # Wait for both phases to complete
        await asyncio.sleep(0.1)
        assert eng.state == ScenarioState.IDLE

    async def test_current_phase_name(self, engine: ScenarioEngine) -> None:
        engine.load_preset("calm")
        await engine.start()
        await asyncio.sleep(0.01)
        assert engine.current_phase_name == "calm"
        engine.stop()
