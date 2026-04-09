"""Risk snapshot and protocol."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from app.modules.risk_engine.interfaces.stress import StressScenario, StressTestResult
    from app.modules.risk_engine.interfaces.var import VaRMethod, VaRResult


class RiskSnapshot(BaseModel):
    """Complete risk snapshot for a portfolio."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    portfolio_id: UUID
    nav: Decimal
    var_95_1d: Decimal
    var_99_1d: Decimal
    expected_shortfall_95: Decimal
    max_drawdown: Decimal
    sharpe_ratio: Decimal | None = None
    snapshot_at: datetime


class RiskReader(Protocol):
    """Public read interface for other modules."""

    async def get_latest_snapshot(self, portfolio_id: UUID) -> RiskSnapshot | None: ...

    async def calculate_var(
        self,
        portfolio_id: UUID,
        method: VaRMethod,
        confidence: float,
        horizon_days: int,
    ) -> VaRResult: ...

    async def run_stress_test(
        self,
        portfolio_id: UUID,
        scenario: StressScenario,
    ) -> StressTestResult: ...
