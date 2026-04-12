"""Price validation — spread checks, staleness detection, positivity.

Stateless validators run against incoming price snapshots before they
are persisted or published. Each check returns a ``ValidationResult``
with pass/fail and a human-readable reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

ZERO = Decimal(0)


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of a single price validation check."""

    valid: bool
    check: str
    message: str


@dataclass(frozen=True)
class PriceValidationReport:
    """Aggregate result of all checks on a single price snapshot."""

    instrument_id: str
    results: list[ValidationResult]

    @property
    def valid(self) -> bool:
        return all(r.valid for r in self.results)

    @property
    def failures(self) -> list[ValidationResult]:
        return [r for r in self.results if not r.valid]


class PriceValidator:
    """Configurable price validator with spread, staleness, and positivity checks.

    Args:
        max_spread_bps: maximum bid-ask spread in basis points (default 500 = 5%)
        max_staleness: maximum age of a price before it's considered stale
        allow_zero_price: whether a zero mid price is accepted (default False)
    """

    def __init__(
        self,
        *,
        max_spread_bps: Decimal = Decimal("500"),
        max_staleness: timedelta = timedelta(minutes=15),
        allow_zero_price: bool = False,
    ) -> None:
        self.max_spread_bps = max_spread_bps
        self.max_staleness = max_staleness
        self.allow_zero_price = allow_zero_price

    def validate(
        self,
        *,
        instrument_id: str,
        bid: Decimal,
        ask: Decimal,
        mid: Decimal,
        timestamp: datetime,
        now: datetime | None = None,
    ) -> PriceValidationReport:
        """Run all validation checks against a price snapshot."""
        now = now or datetime.now(UTC)
        results: list[ValidationResult] = [
            self._check_positivity(bid, ask, mid),
            self._check_spread(bid, ask, mid),
            self._check_staleness(timestamp, now),
            self._check_bid_ask_order(bid, ask),
        ]
        return PriceValidationReport(instrument_id=instrument_id, results=results)

    def _check_positivity(
        self, bid: Decimal, ask: Decimal, mid: Decimal
    ) -> ValidationResult:
        """Prices must be non-negative; mid must be positive unless allow_zero_price."""
        if bid < ZERO or ask < ZERO:
            return ValidationResult(
                valid=False,
                check="positivity",
                message=f"Negative price: bid={bid}, ask={ask}",
            )
        if not self.allow_zero_price and mid <= ZERO:
            return ValidationResult(
                valid=False,
                check="positivity",
                message=f"Zero or negative mid price: {mid}",
            )
        return ValidationResult(valid=True, check="positivity", message="OK")

    def _check_spread(
        self, bid: Decimal, ask: Decimal, mid: Decimal
    ) -> ValidationResult:
        """Bid-ask spread must not exceed max_spread_bps."""
        if mid <= ZERO:
            # Can't compute spread without a positive mid
            return ValidationResult(
                valid=True, check="spread", message="Skipped (zero mid)"
            )
        spread_bps = ((ask - bid) / mid) * Decimal("10000")
        if spread_bps > self.max_spread_bps:
            return ValidationResult(
                valid=False,
                check="spread",
                message=f"Spread {spread_bps:.1f} bps exceeds limit {self.max_spread_bps} bps",
            )
        return ValidationResult(valid=True, check="spread", message="OK")

    def _check_staleness(
        self, timestamp: datetime, now: datetime
    ) -> ValidationResult:
        """Price must not be older than max_staleness."""
        age = now - timestamp
        if age > self.max_staleness:
            minutes = age.total_seconds() / 60
            return ValidationResult(
                valid=False,
                check="staleness",
                message=f"Price is {minutes:.1f}m old (limit {self.max_staleness.total_seconds() / 60:.0f}m)",
            )
        return ValidationResult(valid=True, check="staleness", message="OK")

    def _check_bid_ask_order(self, bid: Decimal, ask: Decimal) -> ValidationResult:
        """Ask must be >= bid (crossed market is invalid)."""
        if ask < bid:
            return ValidationResult(
                valid=False,
                check="bid_ask_order",
                message=f"Crossed market: bid={bid} > ask={ask}",
            )
        return ValidationResult(valid=True, check="bid_ask_order", message="OK")
