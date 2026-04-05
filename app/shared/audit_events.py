"""Canonical audit event type registry.

Every event_type string used in audit logging or Kafka publishing MUST be
defined here. This prevents typos, enables IDE autocomplete, and makes it
trivial to discover all event types in the system.
"""

from __future__ import annotations

from enum import StrEnum


class AuditEventType(StrEnum):
    """All event types used across the platform.

    Naming convention: ``<domain>.<entity>.<action>``

    StrEnum so the value is the string itself — works directly with
    Kafka event_type fields and audit log columns without ``.value``.
    """

    # -- Admin / Platform --------------------------------------------------
    ADMIN_USER_CREATED = "admin.user.created"
    ADMIN_USER_UPDATED = "admin.user.updated"
    ADMIN_OPERATOR_CREATED = "admin.operator.created"
    ADMIN_OPERATOR_UPDATED = "admin.operator.updated"
    ADMIN_FUND_CREATED = "admin.fund.created"
    ADMIN_FUND_UPDATED = "admin.fund.updated"
    ADMIN_ACCESS_GRANTED = "admin.access.granted"
    ADMIN_ACCESS_REVOKED = "admin.access.revoked"
    AUTH_AGENT_TOKEN_CREATED = "auth.agent_token.created"
    AUTH_TOKEN_REVOKED = "auth.token.revoked"
    AUTH_USER_TOKENS_REVOKED = "auth.user_tokens.revoked"

    # -- Orders ------------------------------------------------------------
    ORDER_CREATED = "order.created"
    ORDER_REJECTED = "order.rejected"
    ORDER_CANCELLED = "order.cancelled"
    ORDER_FILLED = "order.filled"

    # -- Trades ------------------------------------------------------------
    TRADE_BUY = "trade.buy"
    TRADE_SELL = "trade.sell"
    TRADE_APPROVED = "trade.approved"
    TRADE_REJECTED = "trade.rejected"

    # -- Compliance --------------------------------------------------------
    COMPLIANCE_RULE_CREATED = "compliance.rule.created"
    COMPLIANCE_RULE_UPDATED = "compliance.rule.updated"
    COMPLIANCE_VIOLATION = "compliance.violation"
    COMPLIANCE_VIOLATION_RESOLVED = "compliance.violation.resolved"
    COMPLIANCE_VIOLATION_WAIVED = "compliance.violation.waived"

    # -- Positions / PnL ---------------------------------------------------
    POSITION_CHANGED = "position.changed"
    PNL_REALIZED = "pnl.realized"
    PNL_MARK_TO_MARKET = "pnl.mark_to_market"

    # -- Market Data -------------------------------------------------------
    PRICE_UPDATED = "price.updated"

    # -- Exposure ----------------------------------------------------------
    EXPOSURE_UPDATED = "exposure.updated"

    # -- Risk --------------------------------------------------------------
    RISK_UPDATED = "risk.updated"

    # -- Cash Management ---------------------------------------------------
    CASH_SETTLEMENT_CREATED = "cash.settlement.created"
    CASH_SETTLEMENT_SETTLED = "cash.settlement.settled"
