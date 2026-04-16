"""SQLAlchemy models for backtesting — stored in platform schema."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import Base


class BacktestRunRecord(Base):
    """Persisted backtest run with configuration, results, and trades."""

    __tablename__ = "backtest_runs"
    __table_args__ = (
        Index("ix_backtest_status", "status"),
        Index("ix_backtest_strategy", "strategy_name"),
        {"schema": "platform"},
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    fund_slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    strategy_name: Mapped[str] = mapped_column(String(128), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    results: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    equity_curve: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    trades: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
