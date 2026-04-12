"""Pure rule evaluation engine — no I/O, no repository deps."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from app.modules.compliance.interfaces import (
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
    restricted_instruments: set[str] = field(default_factory=set)


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
    """Checks if any position is on the restricted list.

    The restricted set is built from two sources (union):
    1. ``restricted_instruments`` inlined in rule parameters (legacy)
    2. ``_restricted_set`` on PortfolioState, populated from the
       ``restricted_instruments`` table at evaluation time
    """

    def evaluate(
        self,
        state: PortfolioState,
        rule: RuleDefinition,
    ) -> EvaluationResult:
        # Legacy: inline list from rule params
        restricted_raw = rule.parameters.get("restricted_instruments", [])
        restricted: list[str] = (
            list(restricted_raw) if isinstance(restricted_raw, (list, tuple)) else []
        )
        restricted_set = {r.upper() for r in restricted}

        # Merge with table-sourced restricted set on state
        if state.restricted_instruments:
            restricted_set |= {r.upper() for r in state.restricted_instruments}

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


class AggregateExposureEvaluator(RuleEvaluator):
    """Checks aggregate exposure by entity (e.g. issuer, counterparty) as % of NAV.

    Parameters:
        max_pct: maximum allowed aggregate exposure percentage
        group_by: position attribute to group by (default "instrument_id")
        entity: optional specific entity value to check
    """

    def evaluate(
        self,
        state: PortfolioState,
        rule: RuleDefinition,
    ) -> EvaluationResult:
        max_pct = Decimal(str(rule.parameters.get("max_pct", 100)))
        group_by = str(rule.parameters.get("group_by", "instrument_id"))
        target_entity = rule.parameters.get("entity")

        if state.nav <= 0:
            return EvaluationResult(
                rule_id=rule.id,
                rule_name=rule.name,
                passed=True,
                severity=rule.severity,
                message="NAV is zero; no aggregate exposure check.",
            )

        # Group positions by the specified attribute
        entity_totals: dict[str, Decimal] = {}
        for pos in state.positions.values():
            entity = getattr(pos, group_by, pos.instrument_id) or "Unknown"
            entity_totals[entity] = entity_totals.get(entity, Decimal(0)) + abs(pos.market_value)

        if target_entity:
            entities = {str(target_entity): entity_totals.get(str(target_entity), Decimal(0))}
        else:
            entities = entity_totals

        worst_entity = ""
        worst_pct = Decimal(0)
        for entity, total in entities.items():
            pct = (total / state.nav) * 100
            if pct > worst_pct:
                worst_pct = pct
                worst_entity = entity

        passed = worst_pct <= max_pct
        return EvaluationResult(
            rule_id=rule.id,
            rule_name=rule.name,
            passed=passed,
            severity=rule.severity,
            message=(
                f"Aggregate exposure to '{worst_entity}' is {worst_pct:.2f}% of NAV (limit {max_pct}%)"
                if not passed
                else "All aggregate exposures within limit."
            ),
            current_value=worst_pct,
            limit_value=max_pct,
        )


class AssetClassLimitEvaluator(RuleEvaluator):
    """Checks aggregate asset class exposure as % of NAV.

    Parameters:
        max_pct: maximum allowed percentage for a single asset class
        asset_class: optional specific asset class to check
    """

    def evaluate(
        self,
        state: PortfolioState,
        rule: RuleDefinition,
    ) -> EvaluationResult:
        max_pct = Decimal(str(rule.parameters.get("max_pct", 100)))
        target_class = rule.parameters.get("asset_class")

        if state.nav <= 0:
            return EvaluationResult(
                rule_id=rule.id,
                rule_name=rule.name,
                passed=True,
                severity=rule.severity,
                message="NAV is zero; no asset class check.",
            )

        class_totals: dict[str, Decimal] = {}
        for pos in state.positions.values():
            ac = pos.asset_class or "Unknown"
            class_totals[ac] = class_totals.get(ac, Decimal(0)) + abs(pos.market_value)

        if target_class:
            classes = {str(target_class): class_totals.get(str(target_class), Decimal(0))}
        else:
            classes = class_totals

        worst_class = ""
        worst_pct = Decimal(0)
        for ac, total in classes.items():
            pct = (total / state.nav) * 100
            if pct > worst_pct:
                worst_pct = pct
                worst_class = ac

        passed = worst_pct <= max_pct
        return EvaluationResult(
            rule_id=rule.id,
            rule_name=rule.name,
            passed=passed,
            severity=rule.severity,
            message=(
                f"Asset class '{worst_class}' is {worst_pct:.2f}% of NAV (limit {max_pct}%)"
                if not passed
                else "All asset classes within limit."
            ),
            current_value=worst_pct,
            limit_value=max_pct,
        )


class LeverageLimitEvaluator(RuleEvaluator):
    """Checks gross notional / NAV ratio against a maximum leverage limit.

    Parameters:
        max_leverage: maximum allowed leverage ratio (e.g. 2.0 means 200% gross)
    """

    def evaluate(
        self,
        state: PortfolioState,
        rule: RuleDefinition,
    ) -> EvaluationResult:
        max_leverage = Decimal(str(rule.parameters.get("max_leverage", 1)))

        if state.nav <= 0:
            return EvaluationResult(
                rule_id=rule.id,
                rule_name=rule.name,
                passed=True,
                severity=rule.severity,
                message="NAV is zero; no leverage check.",
            )

        gross_notional = sum(abs(pos.market_value) for pos in state.positions.values())
        leverage = gross_notional / state.nav

        passed = leverage <= max_leverage
        return EvaluationResult(
            rule_id=rule.id,
            rule_name=rule.name,
            passed=passed,
            severity=rule.severity,
            message=(
                f"Leverage is {leverage:.2f}x (limit {max_leverage}x)"
                if not passed
                else f"Leverage {leverage:.2f}x is within limit."
            ),
            current_value=leverage,
            limit_value=max_leverage,
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
    RuleType.AGGREGATE_EXPOSURE: AggregateExposureEvaluator(),
    RuleType.ASSET_CLASS_LIMIT: AssetClassLimitEvaluator(),
    RuleType.LEVERAGE_LIMIT: LeverageLimitEvaluator(),
}
