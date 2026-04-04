"""Scenario control endpoints — test harness for market regime simulation."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from .engine import PRESETS, ScenarioState

router = APIRouter(prefix="/scenarios", tags=["Scenarios"])


class ScenarioStatusResponse(BaseModel):
    state: str
    active_scenario: str | None = None
    current_phase: str | None = None
    instruments: int = 0
    uptime_seconds: float = 0.0


class PresetInfo(BaseModel):
    name: str
    description: str
    phases: int


def _get_engine(request: Request):  # noqa: ANN202
    return request.app.state.scenario_engine


def _get_market_data(request: Request):  # noqa: ANN202
    return request.app.state.market_data_service


@router.get("/state", response_model=ScenarioStatusResponse)
async def get_state(request: Request) -> ScenarioStatusResponse:
    """Get current scenario status."""
    engine = _get_engine(request)
    market_data = _get_market_data(request)
    started_at = market_data.started_at

    uptime = 0.0
    if started_at:
        uptime = (datetime.now(UTC) - started_at).total_seconds()

    simulator = market_data.simulator
    return ScenarioStatusResponse(
        state=engine.state,
        active_scenario=engine.active_scenario_name,
        current_phase=engine.current_phase_name,
        instruments=len(simulator.universe) if simulator else 0,
        uptime_seconds=round(uptime, 1),
    )


@router.get("/presets", response_model=list[PresetInfo])
async def list_presets() -> list[PresetInfo]:
    """List available scenario presets."""
    return [
        PresetInfo(name=s.name, description=s.description, phases=len(s.phases))
        for s in PRESETS.values()
    ]


@router.post("/load/{preset_name}")
async def load_preset(request: Request, preset_name: str) -> dict[str, str]:
    """Load a scenario preset and start it."""
    engine = _get_engine(request)
    try:
        engine.load_preset(preset_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    await engine.start()
    return {"status": "started", "scenario": preset_name}


@router.post("/stop")
async def stop_scenario(request: Request) -> dict[str, str]:
    """Stop the current scenario and reset to calm regime."""
    engine = _get_engine(request)
    if engine.state != ScenarioState.RUNNING:
        raise HTTPException(status_code=400, detail="No scenario running")
    engine.stop()
    return {"status": "stopped"}


@router.post("/reset")
async def reset(request: Request) -> dict[str, str]:
    """Full reset — stop scenario and clear state."""
    engine = _get_engine(request)
    engine.reset()
    return {"status": "reset"}
