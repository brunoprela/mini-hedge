"""Pure rule evaluation engine — no I/O, no repository deps."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from app.modules.compliance.interface import (
    EvaluationResult,
    RuleDefinition,
    RuleType,
)

# ---------------------------------------------------------------------------
# Portfolio state snapshot used for evaluation
# ---------------------------------------------------------------------------


@dataclass
class PositionInfo:
    """Single position within a portfolio snapshot."""

    instrument_id: str
    quantity: Decimal
    market_value: Decimal
    asset_class: str = ""
    sector: str = ""
    country: str = ""


@dataclass
class PortfolioState:
    """Snapshot of portfolio state for rule evaluation."""

    portfolio_id: UUID
    positions: dict[str, PositionInfo] = field(default_factory=dict)
    nav: Decimal = Decimal(0)


# ---------------------------------------------------------------------------
# Abstract evaluator
# ---------------------------------------------------------------------------


class RuleEvaluator(ABC):
    """Base class for compliance rule evaluators."""

    @abstractmethod
    def evaluate(
        self,
        state: PortfolioState,
        rule: RuleDefinition,
    ) -> EvaluationResult: ...


# ---------------------------------------------------------------------------
# Concrete evaluators
# ---------------------------------------------------------------------------


class ConcentrationLimitEvaluator(RuleEvaluator):
    """Checks single-name concentration as % of NAV."""

    def evaluate(
        self,
        state: PortfolioState,
        rule: RuleDefinition,
    ) -> EvaluationResult:
        max_pct = Decimal(str(rule.parameters.get("max_pct", 100)))
        if state.nav <= 0:
            return EvaluationResult(
                rule_id=rule.id,
                rule_name=rule.name,
                passed=True,
                severity=rule.severity,
                message="NAV is zero; no concentration check.",
            )

        worst_name = ""
        worst_pct = Decimal(0)
        for pos in state.positions.values():
            pct = (abs(pos.market_value) / state.nav) * 100
            if pct > worst_pct:
                worst_pct = pct
                worst_name = pos.instrument_id

        passed = worst_pct <= max_pct
        return EvaluationResult(
            rule_id=rule.id,
            rule_name=rule.name,
            passed=passed,
            severity=rule.severity,
            message=(
                f"{worst_name} is {worst_pct:.2f}% of NAV (limit {max_pct}%)"
                if not passed
                else "All positions within concentration limit."
            ),
            current_value=worst_pct,
            limit_value=max_pct,
        )


class SectorLimitEvaluator(RuleEvaluator):
    """Checks aggregate sector exposure as % of NAV."""

    def evaluate(
        self,
        state: PortfolioState,
        rule: RuleDefinition,
    ) -> EvaluationResult:
        max_pct = Decimal(str(rule.parameters.get("max_pct", 100)))
        target_sector = str(rule.parameters.get("sector", ""))

        if state.nav <= 0:
            return EvaluationResult(
                rule_id=rule.id,
                rule_name=rule.name,
                passed=True,
                severity=rule.severity,
                message="NAV is zero; no sector check.",
            )

        sector_totals: dict[str, Decimal] = {}
        for pos in state.positions.values():
            sector = pos.sector or "Unknown"
            sector_totals[sector] = sector_totals.get(sector, Decimal(0)) + abs(pos.market_value)

        # Check specific sector or find worst sector
        if target_sector:
            sectors_to_check = {target_sector: sector_totals.get(target_sector, Decimal(0))}
        else:
            sectors_to_check = sector_totals

        worst_sector = ""
        worst_pct = Decimal(0)
        for sector, total in sectors_to_check.items():
            pct = (total / state.nav) * 100
            if pct > worst_pct:
                worst_pct = pct
                worst_sector = sector

        passed = worst_pct <= max_pct
        return EvaluationResult(
            rule_id=rule.id,
            rule_name=rule.name,
            passed=passed,
            severity=rule.severity,
            message=(
                f"Sector '{worst_sector}' is {worst_pct:.2f}% of NAV (limit {max_pct}%)"
                if not passed
                else "All sectors within limit."
            ),
            current_value=worst_pct,
            limit_value=max_pct,
        )


class CountryLimitEvaluator(RuleEvaluator):
    """Checks aggregate country exposure as % of NAV."""

    def evaluate(
        self,
        state: PortfolioState,
        rule: RuleDefinition,
    ) -> EvaluationResult:
        max_pct = Decimal(str(rule.parameters.get("max_pct", 100)))
        target_country = str(rule.parameters.get("country", ""))

        if state.nav <= 0:
            return EvaluationResult(
                rule_id=rule.id,
                rule_name=rule.name,
                passed=True,
                severity=rule.severity,
                message="NAV is zero; no country check.",
            )

        country_totals: dict[str, Decimal] = {}
        for pos in state.positions.values():
            country = pos.country or "Unknown"
            country_totals[country] = country_totals.get(country, Decimal(0)) + abs(
                pos.market_value
            )

        if target_country:
            countries = {target_country: country_totals.get(target_country, Decimal(0))}
        else:
            countries = country_totals

        worst_country = ""
        worst_pct = Decimal(0)
        for country, total in countries.items():
            pct = (total / state.nav) * 100
            if pct > worst_pct:
                worst_pct = pct
                worst_country = country

        passed = worst_pct <= max_pct
        return EvaluationResult(
            rule_id=rule.id,
            rule_name=rule.name,
            passed=passed,
            severity=rule.severity,
            message=(
                f"Country '{worst_country}' is {worst_pct:.2f}% of NAV (limit {max_pct}%)"
                if not passed
                else "All countries within limit."
            ),
            current_value=worst_pct,
            limit_value=max_pct,
        )


class RestrictedListEvaluator(RuleEvaluator):
    """Checks if any position is on the restricted list."""

    def evaluate(
        self,
        state: PortfolioState,
        rule: RuleDefinition,
    ) -> EvaluationResult:
        restricted: list[str] = list(
            rule.parameters.get("restricted_instruments", [])  # type: ignore[arg-type]
        )
        restricted_set = {r.upper() for r in restricted}

        violations = [iid for iid in state.positions if iid.upper() in restricted_set]

        passed = len(violations) == 0
        return EvaluationResult(
            rule_id=rule.id,
            rule_name=rule.name,
            passed=passed,
            severity=rule.severity,
            message=(
                f"Restricted instruments held: {', '.join(violations)}"
                if not passed
                else "No restricted instruments held."
            ),
        )


class ShortSellingEvaluator(RuleEvaluator):
    """Checks if short positions exist when not allowed."""

    def evaluate(
        self,
        state: PortfolioState,
        rule: RuleDefinition,
    ) -> EvaluationResult:
        allow_short = rule.parameters.get("allow_short", False)
        if allow_short:
            return EvaluationResult(
                rule_id=rule.id,
                rule_name=rule.name,
                passed=True,
                severity=rule.severity,
                message="Short selling is permitted.",
            )

        shorts = [pos.instrument_id for pos in state.positions.values() if pos.quantity < 0]

        passed = len(shorts) == 0
        return EvaluationResult(
            rule_id=rule.id,
            rule_name=rule.name,
            passed=passed,
            severity=rule.severity,
            message=(
                f"Short positions found: {', '.join(shorts)}"
                if not passed
                else "No short positions."
            ),
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

EVALUATOR_REGISTRY: dict[RuleType, RuleEvaluator] = {
    RuleType.CONCENTRATION_LIMIT: ConcentrationLimitEvaluator(),
    RuleType.SECTOR_LIMIT: SectorLimitEvaluator(),
    RuleType.COUNTRY_LIMIT: CountryLimitEvaluator(),
    RuleType.RESTRICTED_LIST: RestrictedListEvaluator(),
    RuleType.SHORT_SELLING: ShortSellingEvaluator(),
}
