"""Broker scorecard service — tracks execution quality metrics per broker.

Scorecards are updated after every fill with exponential moving averages
so recent performance is weighted more heavily.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from app.modules.orders.interfaces import BrokerScorecard
from app.modules.orders.models.broker_scorecard import BrokerScorecardRecord

if TYPE_CHECKING:
    from app.modules.orders.scorecard.repositories import ScorecardRepository
    from app.shared.database import TenantSessionFactory

logger = structlog.get_logger()

# EMA smoothing factor — higher = more weight on recent observations
_EMA_ALPHA = Decimal("0.1")


class ScorecardService:
    """Tracks and updates broker execution quality metrics."""

    def __init__(
        self,
        *,
        scorecard_repo: ScorecardRepository,
        session_factory: TenantSessionFactory,
    ) -> None:
        self._scorecard_repo = scorecard_repo
        self._session_factory = session_factory

    async def record_fill(
        self,
        broker_id: str,
        slippage_bps: Decimal,
        fill_time_ms: int,
        commission_bps: Decimal,
        fund_slug: str,
        instrument_class: str | None = None,
    ) -> None:
        """Update scorecard after a fill."""
        try:
            async with self._session_factory.fund_scope(fund_slug) as session:
                record = await self._scorecard_repo.get_by_broker(
                    broker_id,
                    instrument_class,
                    session=session,
                )
                if record is None:
                    record = BrokerScorecardRecord(
                        id=str(uuid4()),
                        broker_id=broker_id,
                        instrument_class=instrument_class,
                        period_start=datetime.now(UTC),
                    )

                record.total_orders += 1
                record.total_fills += 1
                record.period_end = datetime.now(UTC)

                # Update fill rate
                if record.total_orders > 0:
                    record.fill_rate = Decimal(
                        str(record.total_fills / record.total_orders)
                    ).quantize(Decimal("0.0001"))

                # EMA update for slippage
                record.avg_slippage_bps = _ema(
                    record.avg_slippage_bps,
                    slippage_bps,
                )
                # EMA update for fill time
                record.avg_fill_time_ms = int(
                    float(record.avg_fill_time_ms) * (1 - float(_EMA_ALPHA))
                    + fill_time_ms * float(_EMA_ALPHA)
                )
                # EMA update for cost
                record.avg_cost_bps = _ema(
                    record.avg_cost_bps,
                    commission_bps + slippage_bps,
                )

                await self._scorecard_repo.upsert(record, session=session)
        except Exception:
            logger.exception("scorecard_update_failed", broker_id=broker_id)

    async def record_reject(
        self,
        broker_id: str,
        fund_slug: str,
        instrument_class: str | None = None,
    ) -> None:
        """Update scorecard after a broker rejection."""
        try:
            async with self._session_factory.fund_scope(fund_slug) as session:
                record = await self._scorecard_repo.get_by_broker(
                    broker_id,
                    instrument_class,
                    session=session,
                )
                if record is None:
                    record = BrokerScorecardRecord(
                        id=str(uuid4()),
                        broker_id=broker_id,
                        instrument_class=instrument_class,
                        period_start=datetime.now(UTC),
                    )

                record.total_orders += 1
                record.total_rejects += 1
                record.period_end = datetime.now(UTC)

                if record.total_orders > 0:
                    record.fill_rate = Decimal(
                        str(record.total_fills / record.total_orders)
                    ).quantize(Decimal("0.0001"))

                await self._scorecard_repo.upsert(record, session=session)
        except Exception:
            logger.exception("scorecard_reject_failed", broker_id=broker_id)

    async def get_scorecard(
        self,
        broker_id: str,
        fund_slug: str,
        instrument_class: str | None = None,
    ) -> BrokerScorecard | None:
        async with self._session_factory.fund_scope(fund_slug) as session:
            record = await self._scorecard_repo.get_by_broker(
                broker_id,
                instrument_class,
                session=session,
            )
            if record is None:
                return None
            return _to_scorecard(record)

    async def get_all_scorecards(
        self,
        fund_slug: str,
    ) -> list[BrokerScorecard]:
        async with self._session_factory.fund_scope(fund_slug) as session:
            records = await self._scorecard_repo.get_all(session=session)
            return [_to_scorecard(r) for r in records]


def _ema(current: Decimal, new_value: Decimal) -> Decimal:
    """Exponential moving average update."""
    return (current * (Decimal("1") - _EMA_ALPHA) + new_value * _EMA_ALPHA).quantize(
        Decimal("0.00000001")
    )


def _to_scorecard(record: BrokerScorecardRecord) -> BrokerScorecard:
    return BrokerScorecard(
        broker_id=record.broker_id,
        instrument_class=record.instrument_class,
        total_orders=record.total_orders,
        total_fills=record.total_fills,
        total_rejects=record.total_rejects,
        avg_slippage_bps=record.avg_slippage_bps,
        avg_fill_time_ms=record.avg_fill_time_ms,
        avg_cost_bps=record.avg_cost_bps,
        fill_rate=record.fill_rate,
    )
