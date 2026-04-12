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

    # -- Customer lifecycle ------------------------------------------------
    ADMIN_CUSTOMER_CREATED = "admin.customer.created"
    ADMIN_CUSTOMER_UPDATED = "admin.customer.updated"
    ADMIN_CUSTOMER_OFFBOARDED = "admin.customer.offboarded"
    ADMIN_SERVICING_EDGE_CREATED = "admin.servicing_edge.created"
    ADMIN_SERVICING_EDGE_UPDATED = "admin.servicing_edge.updated"
    ADMIN_SERVICING_EDGE_TERMINATED = "admin.servicing_edge.terminated"

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
    FX_RATE_UPDATED = "fx_rate.updated"

    # -- FX Hedging --------------------------------------------------------
    FX_FORWARD_OPENED = "fx.forward.opened"
    FX_FORWARD_CLOSED = "fx.forward.closed"
    FX_FORWARD_ROLLED = "fx.forward.rolled"
    FX_FORWARD_MTM = "fx.forward.mtm"
    FX_HEDGE_RECOMMENDED = "fx.hedge.recommended"

    # -- Exposure ----------------------------------------------------------
    EXPOSURE_UPDATED = "exposure.updated"

    # -- Risk --------------------------------------------------------------
    RISK_UPDATED = "risk.updated"

    # -- Cash Management ---------------------------------------------------
    CASH_SETTLEMENT_CREATED = "cash.settlement.created"
    CASH_SETTLEMENT_SETTLED = "cash.settlement.settled"

    # -- Capital Accounts --------------------------------------------------
    CAPITAL_SUBSCRIPTION = "capital.subscription"
    CAPITAL_REDEMPTION = "capital.redemption"
    CAPITAL_ALLOCATION = "capital.allocation"

    # -- Investor Operations -----------------------------------------------
    SUBSCRIPTION_SUBMITTED = "investor_ops.subscription.submitted"
    SUBSCRIPTION_KYC_DECIDED = "investor_ops.subscription.kyc_decided"
    SUBSCRIPTION_EXECUTED = "investor_ops.subscription.executed"
    REDEMPTION_SUBMITTED = "investor_ops.redemption.submitted"
    REDEMPTION_GATE_APPLIED = "investor_ops.redemption.gate_applied"
    REDEMPTION_EXECUTED = "investor_ops.redemption.executed"

    # -- Fund Structures ---------------------------------------------------
    MASTER_FEEDER_LINK_CREATED = "fund_structures.link.created"
    MASTER_FEEDER_LINK_UPDATED = "fund_structures.link.updated"
    STRATEGY_BOOK_CREATED = "fund_structures.book.created"
    STRATEGY_BOOK_UPDATED = "fund_structures.book.updated"
    FOF_HOLDING_ADDED = "fund_structures.fof.holding_added"

    # -- Backtesting -------------------------------------------------------
    BACKTEST_SUBMITTED = "backtesting.submitted"
    BACKTEST_COMPLETED = "backtesting.completed"
    BACKTEST_FAILED = "backtesting.failed"

    # -- Quant Research ----------------------------------------------------
    REGIME_DETECTED = "quant_research.regime.detected"
    FACTOR_EXPOSURE_COMPUTED = "quant_research.factor.computed"

    # -- AI Analysis -------------------------------------------------------
    ANALYSIS_COMPLETED = "ai_analysis.completed"
    RESEARCH_NOTE_CREATED = "ai_analysis.note.created"

    # -- Alternative Data --------------------------------------------------
    ALT_DATA_FEED_CREATED = "alt_data.feed.created"
    ALT_DATA_INGESTED = "alt_data.ingested"

    # -- Feature Store -----------------------------------------------------
    FEATURE_REGISTERED = "feature_store.feature.registered"
    FEATURE_COMPUTED = "feature_store.feature.computed"
