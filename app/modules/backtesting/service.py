"""Backtesting service — orchestrates engine runs and persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from app.modules.backtesting.engine import BUILT_IN_SIGNALS, BacktestEngine
from app.modules.backtesting.interface import (
    BacktestConfig,
    BacktestResult,
    BacktestStatus,
    BacktestSummary,
    BacktestTrade,
    EquityCurvePoint,
    MonthlyReturn,
)
from app.modules.backtesting.models import BacktestRunRecord
from app.modules.backtesting.tear_sheet import TearSheet, generate_tear_sheet

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.backtesting.repository import BacktestRepository
    from app.shared.database import TenantSessionFactory
    from app.shared.events import EventBus

logger = structlog.get_logger()

ZERO = Decimal(0)


class BacktestingService:
    """Orchestrates backtest submission, execution, and retrieval."""

    def __init__(
        self,
        repo: BacktestRepository,
        engine: BacktestEngine,
        session_factory: TenantSessionFactory,
        event_bus: EventBus | None = None,
    ) -> None:
        self._repo = repo
        self._engine = engine
        self._session_factory = session_factory
        self._event_bus = event_bus

    async def submit_backtest(
        self,
        config: BacktestConfig,
        price_data: dict[str, list[tuple[date, Decimal]]],
        signal_name: str = "equal_weight",
        *,
        session: AsyncSession | None = None,
    ) -> BacktestSummary:
        """Create and run a backtest using a built-in signal function."""
        signal_fn = BUILT_IN_SIGNALS.get(signal_name)
        if signal_fn is None:
            msg = f"Unknown signal function: {signal_name}"
            raise ValueError(msg)

        # Create the pending record
        record = BacktestRunRecord(
            strategy_name=config.strategy_name,
            config=config.model_dump(mode="json"),
            status=BacktestStatus.PENDING,
        )
        await self._repo.create(record, session=session)
        backtest_id = record.id

        if self._event_bus:
            from app.shared.audit_events import AuditEventType
            from app.shared.events import BaseEvent
            from app.shared.schema_registry import shared_topic

            await self._event_bus.publish(
                shared_topic("audit"),
                BaseEvent(
                    event_type=AuditEventType.BACKTEST_SUBMITTED,
                    data={
                        "backtest_id": backtest_id,
                        "strategy_name": config.strategy_name,
                        "signal_name": signal_name,
                    },
                ),
            )

        # Update to running
        await self._repo.update_status(
            backtest_id,
            BacktestStatus.RUNNING,
            session=session,
        )

        try:
            # For momentum/mean_reversion, wrap signal_fn to inject price history
            if signal_name in ("momentum", "mean_reversion"):
                import functools

                wrapped = functools.partial(signal_fn, _price_history=price_data)
            else:
                wrapped = signal_fn

            result = self._engine.run(config, price_data, wrapped)

            # Persist results
            now = datetime.now(UTC)
            results_dict = {
                "total_return": str(result.total_return),
                "annualized_return": str(result.annualized_return),
                "sharpe_ratio": str(result.sharpe_ratio),
                "max_drawdown": str(result.max_drawdown),
                "volatility": str(result.volatility),
                "calmar_ratio": str(result.calmar_ratio),
                "sortino_ratio": str(result.sortino_ratio),
                "win_rate": str(result.win_rate),
                "profit_factor": str(result.profit_factor),
                "total_trades": result.total_trades,
                "avg_holding_period_days": str(result.avg_holding_period_days),
                "monthly_returns": [mr.model_dump(mode="json") for mr in result.monthly_returns],
            }
            equity_curve_dicts = [pt.model_dump(mode="json") for pt in result.equity_curve]
            trade_dicts = [t.model_dump(mode="json") for t in result.trades]

            await self._repo.update_status(
                backtest_id,
                BacktestStatus.COMPLETED,
                results=results_dict,
                equity_curve=equity_curve_dicts,
                trades=trade_dicts,
                completed_at=now,
                session=session,
            )

            if self._event_bus:
                from app.shared.audit_events import AuditEventType
                from app.shared.events import BaseEvent
                from app.shared.schema_registry import shared_topic

                await self._event_bus.publish(
                    shared_topic("audit"),
                    BaseEvent(
                        event_type=AuditEventType.BACKTEST_COMPLETED,
                        data={
                            "backtest_id": backtest_id,
                            "strategy_name": config.strategy_name,
                            "total_return": str(result.total_return),
                            "sharpe_ratio": str(result.sharpe_ratio),
                            "max_drawdown": str(result.max_drawdown),
                        },
                    ),
                )

            return BacktestSummary(
                id=backtest_id,
                strategy_name=config.strategy_name,
                status=BacktestStatus.COMPLETED,
                total_return=result.total_return,
                sharpe_ratio=result.sharpe_ratio,
                max_drawdown=result.max_drawdown,
                created_at=record.created_at or now,
            )

        except Exception:
            logger.exception("Backtest failed", backtest_id=backtest_id)
            await self._repo.update_status(
                backtest_id,
                BacktestStatus.FAILED,
                error_message="Internal engine error",
                session=session,
            )
            if self._event_bus:
                from app.shared.audit_events import AuditEventType
                from app.shared.events import BaseEvent
                from app.shared.schema_registry import shared_topic

                await self._event_bus.publish(
                    shared_topic("audit"),
                    BaseEvent(
                        event_type=AuditEventType.BACKTEST_FAILED,
                        data={
                            "backtest_id": backtest_id,
                            "strategy_name": config.strategy_name,
                            "error": "Internal engine error",
                        },
                    ),
                )
            raise

    async def get_backtest(
        self,
        backtest_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> BacktestResult | None:
        """Retrieve full backtest result by ID."""
        record = await self._repo.get_by_id(backtest_id, session=session)
        if record is None:
            return None
        return self._record_to_result(record)

    async def list_backtests(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        session: AsyncSession | None = None,
    ) -> list[BacktestSummary]:
        """List backtest runs, optionally filtered by status."""
        records = await self._repo.list_all(
            status=status,
            limit=limit,
            session=session,
        )
        return [self._record_to_summary(r) for r in records]

    async def delete_backtest(
        self,
        backtest_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        """Delete a backtest run."""
        await self._repo.delete(backtest_id, session=session)

    async def get_tear_sheet(
        self,
        backtest_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> TearSheet | None:
        """Generate a full tear sheet for a completed backtest."""
        result = await self.get_backtest(backtest_id, session=session)
        if result is None:
            return None
        return generate_tear_sheet(result)

    async def compare_backtests(
        self,
        backtest_ids: list[str],
        *,
        session: AsyncSession | None = None,
    ) -> list[BacktestSummary]:
        """Compare multiple backtests side by side."""
        summaries: list[BacktestSummary] = []
        for bid in backtest_ids:
            record = await self._repo.get_by_id(bid, session=session)
            if record is not None:
                summaries.append(self._record_to_summary(record))
        return summaries

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _record_to_summary(record: BacktestRunRecord) -> BacktestSummary:
        results = record.results or {}
        return BacktestSummary(
            id=record.id,
            strategy_name=record.strategy_name,
            status=BacktestStatus(record.status),
            total_return=Decimal(results.get("total_return", "0")),
            sharpe_ratio=Decimal(results.get("sharpe_ratio", "0")),
            max_drawdown=Decimal(results.get("max_drawdown", "0")),
            created_at=record.created_at,
        )

    @staticmethod
    def _record_to_result(record: BacktestRunRecord) -> BacktestResult:
        results = record.results or {}
        config = BacktestConfig.model_validate(record.config)

        equity_curve = [EquityCurvePoint.model_validate(pt) for pt in (record.equity_curve or [])]
        trades = [BacktestTrade.model_validate(t) for t in (record.trades or [])]
        monthly_returns = [
            MonthlyReturn.model_validate(mr) for mr in results.get("monthly_returns", [])
        ]

        return BacktestResult(
            id=record.id,
            config=config,
            status=BacktestStatus(record.status),
            total_return=Decimal(results.get("total_return", "0")),
            annualized_return=Decimal(results.get("annualized_return", "0")),
            sharpe_ratio=Decimal(results.get("sharpe_ratio", "0")),
            max_drawdown=Decimal(results.get("max_drawdown", "0")),
            volatility=Decimal(results.get("volatility", "0")),
            calmar_ratio=Decimal(results.get("calmar_ratio", "0")),
            sortino_ratio=Decimal(results.get("sortino_ratio", "0")),
            win_rate=Decimal(results.get("win_rate", "0")),
            profit_factor=Decimal(results.get("profit_factor", "0")),
            total_trades=int(results.get("total_trades", 0)),
            avg_holding_period_days=Decimal(
                results.get("avg_holding_period_days", "0"),
            ),
            equity_curve=equity_curve,
            trades=trades,
            monthly_returns=monthly_returns,
            created_at=record.created_at,
            completed_at=record.completed_at,
        )
