"""Risk engine public interface — Protocol + value objects."""

from app.modules.risk_engine.interfaces.counterparty import (
    CounterpartyExposure,
    CounterpartyInfo,
    CounterpartyType,
)
from app.modules.risk_engine.interfaces.factor import (
    FactorDecomposition,
    FactorExposure,
    RiskFactor,
)
from app.modules.risk_engine.interfaces.liquidity import LiquidityProfile, PositionLiquidity
from app.modules.risk_engine.interfaces.margin import MarginSummary, PositionMargin
from app.modules.risk_engine.interfaces.snapshot import RiskReader, RiskSnapshot
from app.modules.risk_engine.interfaces.stress import (
    PREDEFINED_SCENARIOS,
    StressPositionImpact,
    StressScenario,
    StressScenarioType,
    StressTestResult,
)
from app.modules.risk_engine.interfaces.var import (
    PortfolioReturn,
    VaRContribution,
    VaRMethod,
    VaRResult,
)

__all__ = [
    "CounterpartyExposure",
    "CounterpartyInfo",
    "CounterpartyType",
    "FactorDecomposition",
    "FactorExposure",
    "LiquidityProfile",
    "MarginSummary",
    "PREDEFINED_SCENARIOS",
    "PortfolioReturn",
    "PositionLiquidity",
    "PositionMargin",
    "RiskFactor",
    "RiskReader",
    "RiskSnapshot",
    "StressPositionImpact",
    "StressScenario",
    "StressScenarioType",
    "StressTestResult",
    "VaRContribution",
    "VaRMethod",
    "VaRResult",
]
