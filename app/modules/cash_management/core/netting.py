"""Settlement netting engine — nets obligations by counterparty and currency."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from app.modules.cash_management.models.cash_settlement import CashSettlementRecord

ZERO = Decimal(0)


class NettingResult(BaseModel):
    """Result of netting settlements for a counterparty + currency pair."""

    model_config = ConfigDict(frozen=True)

    counterparty: str
    currency: str
    gross_payable: Decimal
    gross_receivable: Decimal
    net_amount: Decimal  # positive = receivable, negative = payable
    settlement_count: int
    settlement_ids: list[str]


class NettingEngine:
    """Nets settlement obligations by counterparty and currency."""

    def compute_netting(
        self,
        settlements: list[CashSettlementRecord],
        counterparty_map: dict[str, str],
    ) -> list[NettingResult]:
        """Group pending settlements by counterparty + currency and net.

        Parameters
        ----------
        settlements:
            The list of settlement records to net.
        counterparty_map:
            Maps ``instrument_id`` to a counterparty identifier.
        """
        # Bucket: (counterparty, currency) -> list of settlements
        buckets: dict[tuple[str, str], list[CashSettlementRecord]] = defaultdict(list)

        for s in settlements:
            cp = counterparty_map.get(s.instrument_id, "UNKNOWN")
            buckets[(cp, s.currency)].append(s)

        results: list[NettingResult] = []
        for (cp, ccy), group in sorted(buckets.items()):
            gross_receivable = ZERO
            gross_payable = ZERO
            ids: list[str] = []

            for s in group:
                ids.append(s.id)
                if s.settlement_amount > ZERO:
                    gross_receivable += s.settlement_amount
                else:
                    gross_payable += abs(s.settlement_amount)

            results.append(
                NettingResult(
                    counterparty=cp,
                    currency=ccy,
                    gross_payable=gross_payable,
                    gross_receivable=gross_receivable,
                    net_amount=gross_receivable - gross_payable,
                    settlement_count=len(group),
                    settlement_ids=ids,
                )
            )

        return results

    def compute_bilateral_netting(
        self,
        settlements: list[CashSettlementRecord],
        our_counterparty: str,
        their_counterparty: str,
    ) -> list[NettingResult]:
        """Net only between two specific counterparties.

        Filters settlements whose counterparty matches *their_counterparty*
        (using the instrument_id as the counterparty key) and nets them.
        """
        # For bilateral netting we treat instrument_id == their_counterparty
        # as the filter key.
        filtered = [s for s in settlements if s.instrument_id == their_counterparty]

        # Build a trivial counterparty map for filtered settlements
        cp_map = {s.instrument_id: their_counterparty for s in filtered}

        results = self.compute_netting(filtered, cp_map)

        # Tag with our_counterparty context (bilateral)
        return [
            NettingResult(
                counterparty=f"{our_counterparty}<>{r.counterparty}",
                currency=r.currency,
                gross_payable=r.gross_payable,
                gross_receivable=r.gross_receivable,
                net_amount=r.net_amount,
                settlement_count=r.settlement_count,
                settlement_ids=r.settlement_ids,
            )
            for r in results
        ]
