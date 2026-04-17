"""Compliance orchestration — wraps pre-trade checks and post-fill hooks.

Extracted from OrderService to keep compliance concerns in one place. The
orchestrator is deliberately thin: it composes the existing
``ComplianceGateway`` and exposes a pair of lifecycle-oriented methods so
callers don't need to know the precise shape of ``TradeCheckRequest`` or
``ComplianceDecision`` rows.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from app.modules.compliance.interfaces import TradeCheckRequest

if TYPE_CHECKING:
    from app.modules.compliance.interfaces import ComplianceDecision
    from app.modules.orders.core.compliance_gateway import ComplianceGateway
    from app.modules.orders.models.order import OrderFillRecord


class ComplianceOrchestrator:
    """Runs pre-trade checks and post-fill compliance evaluation."""

    def __init__(self, *, compliance_gateway: ComplianceGateway) -> None:
        self._compliance_gateway = compliance_gateway

    async def pre_check(
        self,
        *,
        portfolio_id: UUID,
        instrument_id: str,
        side: str,
        quantity: Decimal,
        limit_price: Decimal | None,
    ) -> tuple[ComplianceDecision, list[dict[str, object]]]:
        """Run a pre-trade compliance check and return the decision + serialized rows.

        The second tuple element is ready to persist on the order record as
        ``compliance_results`` (matches the shape previously built inline).
        """
        request = TradeCheckRequest(
            portfolio_id=portfolio_id,
            instrument_id=instrument_id,
            side=side,
            quantity=quantity,
            price=limit_price or Decimal("100.00"),
        )
        decision = await self._compliance_gateway.check(request)

        compliance_data: list[dict[str, object]] = [
            {
                "rule_id": str(r.rule_id),
                "rule_name": r.rule_name,
                "passed": r.passed,
                "severity": r.severity,
                "message": r.message,
            }
            for r in decision.results
        ]
        return decision, compliance_data

    async def post_fill(self, fill: OrderFillRecord) -> None:
        """Post-fill compliance hook — no-op placeholder for future checks.

        Intended extension point for things like post-trade exposure checks,
        after-the-fact breach detection, or regulatory trade reporting.
        """
        return None
