"""Unit tests for compliance rule evaluators — pure functions, no I/O."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.modules.compliance.core.engine import (
    ConcentrationLimitEvaluator,
    CountryLimitEvaluator,
    PortfolioState,
    PositionInfo,
    RestrictedListEvaluator,
    SectorLimitEvaluator,
    ShortSellingEvaluator,
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


def _state(positions: dict[str, tuple[Decimal, str, str, str]], nav: Decimal) -> PortfolioState:
    """Build a PortfolioState from (market_value, sector, country, asset_class) tuples."""
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
# Concentration limit
# ---------------------------------------------------------------------------


class TestConcentrationLimit:
    evaluator = ConcentrationLimitEvaluator()

    def test_within_limit(self):
        state = _state(
            {"AAPL": (Decimal("200000"), "Tech", "US", "equity")},
            nav=Decimal("1000000"),
        )
        rule = _rule(RuleType.CONCENTRATION_LIMIT, {"max_pct": 25})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True

    def test_exceeds_limit(self):
        state = _state(
            {"AAPL": (Decimal("300000"), "Tech", "US", "equity")},
            nav=Decimal("1000000"),
        )
        rule = _rule(RuleType.CONCENTRATION_LIMIT, {"max_pct": 25})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is False
        assert "AAPL" in result.message

    def test_multiple_positions_worst_checked(self):
        state = _state(
            {
                "AAPL": (Decimal("150000"), "Tech", "US", "equity"),
                "TSLA": (Decimal("350000"), "Tech", "US", "equity"),
                "JNJ": (Decimal("100000"), "Health", "US", "equity"),
            },
            nav=Decimal("600000"),
        )
        rule = _rule(RuleType.CONCENTRATION_LIMIT, {"max_pct": 50})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is False
        assert "TSLA" in result.message

    def test_zero_nav_passes(self):
        state = _state(
            {"AAPL": (Decimal("100000"), "Tech", "US", "equity")},
            nav=Decimal("0"),
        )
        rule = _rule(RuleType.CONCENTRATION_LIMIT, {"max_pct": 25})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True

    def test_exact_limit_passes(self):
        state = _state(
            {"AAPL": (Decimal("250000"), "Tech", "US", "equity")},
            nav=Decimal("1000000"),
        )
        rule = _rule(RuleType.CONCENTRATION_LIMIT, {"max_pct": 25})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True


# ---------------------------------------------------------------------------
# Sector limit
# ---------------------------------------------------------------------------


class TestSectorLimit:
    evaluator = SectorLimitEvaluator()

    def test_within_limit(self):
        state = _state(
            {
                "AAPL": (Decimal("150000"), "Technology", "US", "equity"),
                "MSFT": (Decimal("100000"), "Technology", "US", "equity"),
                "JNJ": (Decimal("250000"), "Healthcare", "US", "equity"),
            },
            nav=Decimal("500000"),
        )
        rule = _rule(RuleType.SECTOR_LIMIT, {"max_pct": 60})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True

    def test_exceeds_limit_worst_sector(self):
        state = _state(
            {
                "AAPL": (Decimal("400000"), "Technology", "US", "equity"),
                "MSFT": (Decimal("200000"), "Technology", "US", "equity"),
                "JNJ": (Decimal("100000"), "Healthcare", "US", "equity"),
            },
            nav=Decimal("700000"),
        )
        # Technology = 600k/700k = 85.7% > 80%
        rule = _rule(RuleType.SECTOR_LIMIT, {"max_pct": 80})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is False
        assert "Technology" in result.message

    def test_specific_sector_filter(self):
        state = _state(
            {
                "AAPL": (Decimal("200000"), "Technology", "US", "equity"),
                "JNJ": (Decimal("800000"), "Healthcare", "US", "equity"),
            },
            nav=Decimal("1000000"),
        )
        rule = _rule(RuleType.SECTOR_LIMIT, {"max_pct": 25, "sector": "Technology"})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True

    def test_zero_nav_passes(self):
        state = _state(
            {"AAPL": (Decimal("100000"), "Technology", "US", "equity")},
            nav=Decimal("0"),
        )
        rule = _rule(RuleType.SECTOR_LIMIT, {"max_pct": 50})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True


# ---------------------------------------------------------------------------
# Country limit
# ---------------------------------------------------------------------------


class TestCountryLimit:
    evaluator = CountryLimitEvaluator()

    def test_within_limit(self):
        state = _state(
            {
                "7203.T": (Decimal("200000"), "Auto", "JP", "equity"),
                "AAPL": (Decimal("800000"), "Technology", "US", "equity"),
            },
            nav=Decimal("1000000"),
        )
        rule = _rule(RuleType.COUNTRY_LIMIT, {"max_pct": 90})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True

    def test_exceeds_limit(self):
        state = _state(
            {
                "7203.T": (Decimal("600000"), "Auto", "JP", "equity"),
                "9984.T": (Decimal("300000"), "Tech", "JP", "equity"),
                "AAPL": (Decimal("100000"), "Technology", "US", "equity"),
            },
            nav=Decimal("1000000"),
        )
        # JP = 900k/1M = 90% > 80%
        rule = _rule(RuleType.COUNTRY_LIMIT, {"max_pct": 80})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is False
        assert "JP" in result.message

    def test_specific_country_filter(self):
        state = _state(
            {
                "7203.T": (Decimal("200000"), "Auto", "JP", "equity"),
                "AAPL": (Decimal("800000"), "Technology", "US", "equity"),
            },
            nav=Decimal("1000000"),
        )
        rule = _rule(RuleType.COUNTRY_LIMIT, {"max_pct": 25, "country": "JP"})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True


# ---------------------------------------------------------------------------
# Restricted list
# ---------------------------------------------------------------------------


class TestRestrictedList:
    evaluator = RestrictedListEvaluator()

    def test_no_restricted_passes(self):
        state = _state(
            {"AAPL": (Decimal("100000"), "Tech", "US", "equity")},
            nav=Decimal("100000"),
        )
        rule = _rule(RuleType.RESTRICTED_LIST, {"restricted_instruments": ["TSLA", "META"]})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True

    def test_holding_restricted_fails(self):
        state = _state(
            {
                "AAPL": (Decimal("100000"), "Tech", "US", "equity"),
                "TSLA": (Decimal("50000"), "Tech", "US", "equity"),
            },
            nav=Decimal("150000"),
        )
        rule = _rule(RuleType.RESTRICTED_LIST, {"restricted_instruments": ["TSLA"]})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is False
        assert "TSLA" in result.message

    def test_case_insensitive_matching(self):
        state = _state(
            {"tsla": (Decimal("50000"), "Tech", "US", "equity")},
            nav=Decimal("50000"),
        )
        rule = _rule(RuleType.RESTRICTED_LIST, {"restricted_instruments": ["TSLA"]})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is False

    def test_empty_restricted_list_passes(self):
        state = _state(
            {"AAPL": (Decimal("100000"), "Tech", "US", "equity")},
            nav=Decimal("100000"),
        )
        rule = _rule(RuleType.RESTRICTED_LIST, {"restricted_instruments": []})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True


# ---------------------------------------------------------------------------
# Short selling
# ---------------------------------------------------------------------------


class TestShortSelling:
    evaluator = ShortSellingEvaluator()

    def _state_with_qty(self, qty: Decimal) -> PortfolioState:
        pos = PositionInfo(
            instrument_id="AAPL",
            quantity=qty,
            market_value=Decimal("100000"),
            sector="Tech",
        )
        return PortfolioState(
            portfolio_id=PORTFOLIO_ID,
            positions={"AAPL": pos},
            nav=Decimal("100000"),
        )

    def test_no_shorts_passes(self):
        state = self._state_with_qty(Decimal("100"))
        rule = _rule(RuleType.SHORT_SELLING, {"allow_short": False})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True

    def test_short_position_fails_when_not_allowed(self):
        state = self._state_with_qty(Decimal("-50"))
        rule = _rule(RuleType.SHORT_SELLING, {"allow_short": False})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is False
        assert "AAPL" in result.message

    def test_short_position_passes_when_allowed(self):
        state = self._state_with_qty(Decimal("-50"))
        rule = _rule(RuleType.SHORT_SELLING, {"allow_short": True})
        result = self.evaluator.evaluate(state, rule)
        assert result.passed is True

    def test_severity_preserved(self):
        state = self._state_with_qty(Decimal("-50"))
        rule = _rule(RuleType.SHORT_SELLING, {"allow_short": False}, severity=Severity.WARNING)
        result = self.evaluator.evaluate(state, rule)
        assert result.severity == Severity.WARNING
