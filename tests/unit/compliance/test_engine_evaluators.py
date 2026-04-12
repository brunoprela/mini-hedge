"""Unit tests for remaining compliance engine evaluators — pure functions, no I/O."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.modules.compliance.core.engine import (
    AggregateExposureEvaluator,
    AssetClassLimitEvaluator,
    CountryLimitEvaluator,
    LeverageLimitEvaluator,
    PortfolioState,
    PositionInfo,
    RestrictedListEvaluator,
)
from app.modules.compliance.interfaces import RuleDefinition, RuleType, Severity

PORTFOLIO_ID = uuid4()
NOW = datetime.now(UTC)


def _rule(
    rule_type: RuleType,
    parameters: dict,
    severity: Severity = Severity.BLOCK,
    name: str = "test_rule",
) -> RuleDefinition:
    return RuleDefinition(
        id=uuid4(),
        name=name,
        rule_type=rule_type,
        severity=severity,
        parameters=parameters,
        is_active=True,
        created_at=NOW,
    )


def _state(
    positions: dict[str, tuple[Decimal, str, str, str]],
    nav: Decimal,
) -> PortfolioState:
    """Build PortfolioState from (market_value, sector, country, asset_class) tuples."""
    pos_dict = {}
    for iid, (mv, sector, country, ac) in positions.items():
        pos_dict[iid] = PositionInfo(
            instrument_id=iid,
            quantity=Decimal(100),
            market_value=mv,
            sector=sector,
            country=country,
            asset_class=ac,
        )
    return PortfolioState(portfolio_id=PORTFOLIO_ID, positions=pos_dict, nav=nav)


# ---------------------------------------------------------------------------
# Country limit — zero NAV (line 173)
# ---------------------------------------------------------------------------


class TestRestrictedListStateSource:
    """Test restricted_instruments sourced from PortfolioState (line 240)."""

    evaluator = RestrictedListEvaluator()

    def test_state_restricted_instruments_detected(self):
        """Restricted instruments on the state (not rule params) should be caught."""
        pos = {
            "AAPL": PositionInfo(
                instrument_id="AAPL",
                quantity=Decimal(100),
                market_value=Decimal("100000"),
            ),
        }
        state = PortfolioState(
            portfolio_id=PORTFOLIO_ID,
            positions=pos,
            nav=Decimal("100000"),
            restricted_instruments={"AAPL"},
        )
        rule = _rule(RuleType.RESTRICTED_LIST, {"restricted_instruments": []})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is False
        assert "AAPL" in result.message

    def test_state_and_param_restricted_merged(self):
        """Both sources are merged — union of state and param restricted lists."""
        pos = {
            "AAPL": PositionInfo(
                instrument_id="AAPL",
                quantity=Decimal(100),
                market_value=Decimal("100000"),
            ),
            "TSLA": PositionInfo(
                instrument_id="TSLA",
                quantity=Decimal(50),
                market_value=Decimal("50000"),
            ),
        }
        state = PortfolioState(
            portfolio_id=PORTFOLIO_ID,
            positions=pos,
            nav=Decimal("150000"),
            restricted_instruments={"TSLA"},
        )
        rule = _rule(RuleType.RESTRICTED_LIST, {"restricted_instruments": ["AAPL"]})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is False
        assert "AAPL" in result.message
        assert "TSLA" in result.message


class TestCountryLimitZeroNav:
    evaluator = CountryLimitEvaluator()

    def test_zero_nav_passes(self):
        state = _state(
            {"7203.T": (Decimal("600000"), "Auto", "JP", "equity")},
            nav=Decimal("0"),
        )
        rule = _rule(RuleType.COUNTRY_LIMIT, {"max_pct": 80})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True
        assert "NAV is zero" in result.message


# ---------------------------------------------------------------------------
# Aggregate exposure evaluator (lines 306-339)
# ---------------------------------------------------------------------------


class TestAggregateExposure:
    evaluator = AggregateExposureEvaluator()

    def test_zero_nav_passes(self):
        state = _state(
            {"AAPL": (Decimal("100000"), "Tech", "US", "equity")},
            nav=Decimal("0"),
        )
        rule = _rule(RuleType.AGGREGATE_EXPOSURE, {"max_pct": 10})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True
        assert "NAV is zero" in result.message

    def test_within_limit(self):
        state = _state(
            {
                "AAPL": (Decimal("100000"), "Tech", "US", "equity"),
                "MSFT": (Decimal("100000"), "Tech", "US", "equity"),
                "JNJ": (Decimal("100000"), "Health", "US", "equity"),
            },
            nav=Decimal("1000000"),
        )
        rule = _rule(RuleType.AGGREGATE_EXPOSURE, {"max_pct": 50, "group_by": "instrument_id"})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True

    def test_exceeds_limit(self):
        state = _state(
            {
                "AAPL": (Decimal("600000"), "Tech", "US", "equity"),
                "MSFT": (Decimal("100000"), "Tech", "US", "equity"),
            },
            nav=Decimal("700000"),
        )
        # AAPL = 600k/700k = 85.7% > 50%
        rule = _rule(RuleType.AGGREGATE_EXPOSURE, {"max_pct": 50, "group_by": "instrument_id"})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is False
        assert "AAPL" in result.message

    def test_group_by_sector(self):
        state = _state(
            {
                "AAPL": (Decimal("400000"), "Tech", "US", "equity"),
                "MSFT": (Decimal("300000"), "Tech", "US", "equity"),
                "JNJ": (Decimal("100000"), "Health", "US", "equity"),
            },
            nav=Decimal("800000"),
        )
        # Tech = 700k/800k = 87.5% > 80%
        rule = _rule(RuleType.AGGREGATE_EXPOSURE, {"max_pct": 80, "group_by": "sector"})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is False
        assert "Tech" in result.message

    def test_specific_entity(self):
        state = _state(
            {
                "AAPL": (Decimal("100000"), "Tech", "US", "equity"),
                "MSFT": (Decimal("800000"), "Tech", "US", "equity"),
            },
            nav=Decimal("1000000"),
        )
        # Only check AAPL = 10% < 50%
        rule = _rule(
            RuleType.AGGREGATE_EXPOSURE,
            {"max_pct": 50, "group_by": "instrument_id", "entity": "AAPL"},
        )
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True

    def test_specific_entity_missing(self):
        """When the target entity is not in positions, its total is zero."""
        state = _state(
            {"AAPL": (Decimal("500000"), "Tech", "US", "equity")},
            nav=Decimal("1000000"),
        )
        rule = _rule(
            RuleType.AGGREGATE_EXPOSURE,
            {"max_pct": 50, "group_by": "instrument_id", "entity": "TSLA"},
        )
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True

    def test_default_group_by(self):
        """Default group_by is instrument_id."""
        state = _state(
            {"AAPL": (Decimal("600000"), "Tech", "US", "equity")},
            nav=Decimal("1000000"),
        )
        rule = _rule(RuleType.AGGREGATE_EXPOSURE, {"max_pct": 50})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is False


# ---------------------------------------------------------------------------
# Asset class limit evaluator (lines 367-398)
# ---------------------------------------------------------------------------


class TestAssetClassLimit:
    evaluator = AssetClassLimitEvaluator()

    def test_zero_nav_passes(self):
        state = _state(
            {"AAPL": (Decimal("100000"), "Tech", "US", "equity")},
            nav=Decimal("0"),
        )
        rule = _rule(RuleType.ASSET_CLASS_LIMIT, {"max_pct": 50})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True
        assert "NAV is zero" in result.message

    def test_within_limit(self):
        state = _state(
            {
                "AAPL": (Decimal("200000"), "Tech", "US", "equity"),
                "AGG": (Decimal("200000"), "Fixed", "US", "bond"),
            },
            nav=Decimal("1000000"),
        )
        rule = _rule(RuleType.ASSET_CLASS_LIMIT, {"max_pct": 50})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True

    def test_exceeds_limit(self):
        state = _state(
            {
                "AAPL": (Decimal("500000"), "Tech", "US", "equity"),
                "MSFT": (Decimal("400000"), "Tech", "US", "equity"),
                "AGG": (Decimal("100000"), "Fixed", "US", "bond"),
            },
            nav=Decimal("1000000"),
        )
        # equity = 900k/1M = 90% > 60%
        rule = _rule(RuleType.ASSET_CLASS_LIMIT, {"max_pct": 60})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is False
        assert "equity" in result.message

    def test_specific_asset_class(self):
        state = _state(
            {
                "AAPL": (Decimal("200000"), "Tech", "US", "equity"),
                "AGG": (Decimal("800000"), "Fixed", "US", "bond"),
            },
            nav=Decimal("1000000"),
        )
        rule = _rule(RuleType.ASSET_CLASS_LIMIT, {"max_pct": 25, "asset_class": "equity"})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True

    def test_specific_asset_class_missing(self):
        """When the target asset class has no positions, its total is zero."""
        state = _state(
            {"AAPL": (Decimal("500000"), "Tech", "US", "equity")},
            nav=Decimal("1000000"),
        )
        rule = _rule(RuleType.ASSET_CLASS_LIMIT, {"max_pct": 50, "asset_class": "bond"})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True

    def test_unknown_asset_class_grouped_as_unknown(self):
        """Positions with empty asset_class fall into 'Unknown'."""
        pos = {
            "AAPL": PositionInfo(
                instrument_id="AAPL",
                quantity=Decimal(100),
                market_value=Decimal("600000"),
                asset_class="",
            ),
        }
        state = PortfolioState(portfolio_id=PORTFOLIO_ID, positions=pos, nav=Decimal("1000000"))
        rule = _rule(RuleType.ASSET_CLASS_LIMIT, {"max_pct": 50})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is False
        assert "Unknown" in result.message


# ---------------------------------------------------------------------------
# Leverage limit evaluator (lines 425-440)
# ---------------------------------------------------------------------------


class TestLeverageLimit:
    evaluator = LeverageLimitEvaluator()

    def test_zero_nav_passes(self):
        state = _state(
            {"AAPL": (Decimal("100000"), "Tech", "US", "equity")},
            nav=Decimal("0"),
        )
        rule = _rule(RuleType.LEVERAGE_LIMIT, {"max_leverage": 2})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True
        assert "NAV is zero" in result.message

    def test_within_limit(self):
        state = _state(
            {"AAPL": (Decimal("100000"), "Tech", "US", "equity")},
            nav=Decimal("200000"),
        )
        # leverage = 100k/200k = 0.5x < 2x
        rule = _rule(RuleType.LEVERAGE_LIMIT, {"max_leverage": 2})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True
        assert "within limit" in result.message

    def test_exceeds_limit(self):
        state = _state(
            {
                "AAPL": (Decimal("500000"), "Tech", "US", "equity"),
                "MSFT": (Decimal("400000"), "Tech", "US", "equity"),
                "TSLA": (Decimal("300000"), "Tech", "US", "equity"),
            },
            nav=Decimal("500000"),
        )
        # gross = 1.2M / 500k = 2.4x > 2x
        rule = _rule(RuleType.LEVERAGE_LIMIT, {"max_leverage": 2})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is False
        assert "2.40" in result.message

    def test_exact_limit_passes(self):
        state = _state(
            {"AAPL": (Decimal("200000"), "Tech", "US", "equity")},
            nav=Decimal("100000"),
        )
        # leverage = 200k/100k = 2.0x == 2x
        rule = _rule(RuleType.LEVERAGE_LIMIT, {"max_leverage": 2})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True

    def test_default_max_leverage(self):
        """Default max_leverage is 1 if not provided."""
        state = _state(
            {"AAPL": (Decimal("200000"), "Tech", "US", "equity")},
            nav=Decimal("100000"),
        )
        # leverage = 2x > 1x default
        rule = _rule(RuleType.LEVERAGE_LIMIT, {})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is False
