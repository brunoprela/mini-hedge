"""In-process compliance gateway — calls PreTradeGate directly."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.compliance.interface import (
        ComplianceDecision,
        TradeCheckRequest,
    )
    from app.modules.compliance.pre_trade import PreTradeGate


class ComplianceGateway:
    """Thin wrapper calling compliance module's PreTradeGate in-process."""

    def __init__(self, *, pre_trade_gate: PreTradeGate) -> None:
        self._gate = pre_trade_gate

    async def check(self, request: TradeCheckRequest) -> ComplianceDecision:
        return await self._gate.check_trade(request)
