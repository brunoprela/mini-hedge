"""Default compliance rule seeds for new funds."""

from __future__ import annotations

from app.modules.compliance.models import ComplianceRuleRecord


def build_seed_compliance_rules(
    fund_slug: str,
) -> list[ComplianceRuleRecord]:
    """Return six sensible default compliance rules for a fund."""
    return [
        ComplianceRuleRecord(
            fund_slug=fund_slug,
            name="Max Single Name 5%",
            rule_type="concentration_limit",
            severity="block",
            parameters={"max_pct": 5},
            is_active=True,
            grace_period_hours=72,  # 3 business days to cure passive breaches
        ),
        ComplianceRuleRecord(
            fund_slug=fund_slug,
            name="Single Name Warning 3%",
            rule_type="concentration_limit",
            severity="warning",
            parameters={"max_pct": 3},
            is_active=True,
        ),
        ComplianceRuleRecord(
            fund_slug=fund_slug,
            name="Max Sector 25%",
            rule_type="sector_limit",
            severity="block",
            parameters={"max_pct": 25},
            is_active=True,
            grace_period_hours=120,  # 5 business days
        ),
        ComplianceRuleRecord(
            fund_slug=fund_slug,
            name="Max Country 40%",
            rule_type="country_limit",
            severity="breach",
            parameters={"max_pct": 40},
            is_active=True,
            grace_period_hours=120,  # 5 business days
        ),
        ComplianceRuleRecord(
            fund_slug=fund_slug,
            name="Regulatory Restricted List",
            rule_type="restricted_list",
            severity="block",
            parameters={"restricted_instruments": []},
            is_active=True,
        ),
        ComplianceRuleRecord(
            fund_slug=fund_slug,
            name="No Naked Shorts",
            rule_type="short_selling",
            severity="block",
            parameters={"allow_short": False},
            is_active=True,
        ),
    ]
