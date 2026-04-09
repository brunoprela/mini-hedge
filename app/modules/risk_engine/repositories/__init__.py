"""Risk engine repositories — one per domain."""

from app.modules.risk_engine.repositories.counterparty import CounterpartyRepository
from app.modules.risk_engine.repositories.counterparty_exposure import (
    CounterpartyExposureRepository,
)
from app.modules.risk_engine.repositories.factor import FactorExposureRepository
from app.modules.risk_engine.repositories.liquidity import LiquidityRepository
from app.modules.risk_engine.repositories.margin import MarginRepository
from app.modules.risk_engine.repositories.snapshot import RiskSnapshotRepository
from app.modules.risk_engine.repositories.stress_position_impact import (
    StressPositionImpactRepository,
)
from app.modules.risk_engine.repositories.stress_test_result import StressTestResultRepository
from app.modules.risk_engine.repositories.var_contribution import VaRContributionRepository
from app.modules.risk_engine.repositories.var_result import VaRResultRepository

__all__ = [
    "CounterpartyExposureRepository",
    "CounterpartyRepository",
    "FactorExposureRepository",
    "LiquidityRepository",
    "MarginRepository",
    "RiskSnapshotRepository",
    "StressPositionImpactRepository",
    "StressTestResultRepository",
    "VaRContributionRepository",
    "VaRResultRepository",
]
