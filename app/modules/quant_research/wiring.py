"""Quant research module wiring — factor research + regime detection."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from app.modules.quant_research.core.factor_engine import (
    compute_momentum_factor,
    compute_quality_factor,
    compute_size_factor,
    compute_value_factor,
    compute_volatility_factor,
)
from app.modules.quant_research.core.regime_detector import RegimeDetector
from app.modules.quant_research.repositories import (
    FactorDefinitionRepository,
    FactorExposureRepository,
    FactorReturnRepository,
    RegimeRepository,
)
from app.modules.quant_research.services import QuantResearchService

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
    """Wire quant research module (factor research + regime detection)."""
    factor_def_repo = FactorDefinitionRepository(sf)
    factor_exp_repo = FactorExposureRepository(sf)
    factor_ret_repo = FactorReturnRepository(sf)
    regime_repo = RegimeRepository(sf)
    regime_detector = RegimeDetector()

    factor_fns = {
        "momentum": compute_momentum_factor,
        "value": compute_value_factor,
        "size": compute_size_factor,
        "quality": compute_quality_factor,
        "volatility": compute_volatility_factor,
    }

    svc = QuantResearchService(
        factor_def_repo=factor_def_repo,
        factor_exp_repo=factor_exp_repo,
        factor_ret_repo=factor_ret_repo,
        regime_repo=regime_repo,
        factor_engine_fns=factor_fns,
        regime_detector=regime_detector,
        session_factory=sf,
        event_bus=event_bus,
    )
    app.state.quant_research_service = svc
    logger.info("quant_research_module_ready")
