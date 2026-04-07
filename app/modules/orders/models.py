"""SQLAlchemy models for orders — stored in the positions schema."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base as Base


class OrderRecord(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_portfolio", "portfolio_id"),
        Index("ix_orders_state", "state"),
        Index("ix_orders_fund", "fund_slug"),
        Index("ix_orders_parent_order_id", "parent_order_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    portfolio_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    instrument_id: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    filled_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, server_default=text("0")
    )
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    avg_fill_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    compliance_results: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    time_in_force: Mapped[str] = mapped_column(String(8), nullable=False)
    fund_slug: Mapped[str] = mapped_column(String(64), nullable=False)

    # Algo execution — parent/child order model
    parent_order_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("positions.orders.id"),
        nullable=True,
    )
    algo_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    algo_params: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_parent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    # Multi-broker routing
    broker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # TCA arrival price capture
    arrival_mid_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    arrival_spread: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    arrival_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class OrderFillRecord(Base):
    __tablename__ = "order_fills"
    __table_args__ = (
        Index("ix_order_fills_order", "order_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    order_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("positions.orders.id"),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    broker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    filled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class BrokerScorecardRecord(Base):
    __tablename__ = "broker_scorecards"
    __table_args__ = (
        Index("ix_broker_scorecards_broker_id", "broker_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    broker_id: Mapped[str] = mapped_column(String(64), nullable=False)
    instrument_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    total_orders: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    total_fills: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    total_rejects: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    avg_slippage_bps: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, server_default=text("0")
    )
    avg_fill_time_ms: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    avg_cost_bps: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, server_default=text("0")
    )
    fill_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, server_default=text("0")
    )
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class RoutingRuleRecord(Base):
    __tablename__ = "routing_rules"
    __table_args__ = (
        Index("ix_routing_rules_fund", "fund_slug"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    fund_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy: Mapped[str | None] = mapped_column(String(64), nullable=True)
    instrument_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    min_size: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    max_size: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    preferred_broker_id: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class RoutingDecisionRecord(Base):
    __tablename__ = "routing_decisions"
    __table_args__ = (
        Index("ix_routing_decisions_order_id", "order_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    order_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    broker_id: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    score: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    score_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    rule_ids_matched: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class TCAResultRecord(Base):
    __tablename__ = "order_tca_results"
    __table_args__ = (
        Index("ix_tca_order_id", "order_id"),
        {"schema": "positions"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    order_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, unique=True)

    # Benchmarks
    arrival_mid_price: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    arrival_spread: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    vwap_benchmark: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)

    # Cost decomposition (basis points)
    total_cost_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    commission_cost_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    spread_cost_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    market_impact_cost_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    timing_cost_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    opportunity_cost_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    implementation_shortfall_bps: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)

    # Participation metrics
    participation_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 6), nullable=True)
    execution_duration_seconds: Mapped[int] = mapped_column(nullable=False)

    # Dollar amounts
    total_cost_usd: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    # Metadata
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
