"""Corporate actions orchestrator — fetches, processes, and persists actions."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from app.modules.corporate_actions.interface import (
    ActionType,
    ProcessedAction,
    ProcessingStatus,
)
from app.modules.corporate_actions.models import ProcessedCorporateActionRecord
from app.modules.corporate_actions.processor import compute_adjustments
from app.shared.events import BaseEvent
from app.shared.schema_registry import fund_topic

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.corporate_actions.repository import CorporateActionsRepository
    from app.modules.positions.service import PositionService
    from app.shared.adapters import CorporateActionsAdapter
    from app.shared.database import TenantSessionFactory
    from app.shared.events import EventBus

logger = structlog.get_logger()


class CorporateActionsService:
    """Orchestrates corporate action processing for a fund."""

    def __init__(
        self,
        *,
        session_factory: TenantSessionFactory,
        repo: CorporateActionsRepository,
        corporate_actions_adapter: CorporateActionsAdapter,
        event_bus: EventBus,
        position_service: PositionService,
    ) -> None:
        self._session_factory = session_factory
        self._repo = repo
        self._adapter = corporate_actions_adapter
        self._event_bus = event_bus
        self._position_service = position_service

    async def fetch_and_process(
        self,
        fund_slug: str,
        portfolio_id: str,
        start_date: date,
        end_date: date,
        *,
        session: AsyncSession | None = None,
    ) -> list[ProcessedAction]:
        """Fetch corporate actions from the adapter and process each one.

        Steps for each action:
        1. Check idempotency — skip if already processed.
        2. Compute position adjustments via the pure processor.
        3. Publish trade events for splits (position changes).
        4. Persist the ProcessedCorporateAction record.
        5. Publish ``corporate_actions.processed`` event.
        """
        actions = await self._adapter.get_actions(
            start=start_date,
            end=end_date,
        )

        results: list[ProcessedAction] = []
        for action in actions:
            processed = await self._process_single(
                action,
                fund_slug=fund_slug,
                portfolio_id=portfolio_id,
                session=session,
            )
            results.append(processed)

        return results

    async def _process_single(
        self,
        action: object,
        *,
        fund_slug: str,
        portfolio_id: str,
        session: AsyncSession | None = None,
    ) -> ProcessedAction:
        """Process a single corporate action with idempotency."""
        from app.shared.adapters import CorporateAction

        assert isinstance(action, CorporateAction)

        # 1. Idempotency check
        existing = await self._repo.get_by_action_id(action.action_id, session=session)
        if existing is not None:
            logger.info(
                "corporate_action_already_processed",
                action_id=action.action_id,
                status=existing.status,
            )
            return self._to_processed_action(existing)

        # 2. Look up current position for this instrument
        position = await self._position_service.get_position(
            UUID(portfolio_id), action.instrument_id, session=session
        )
        quantity = position.quantity if position else Decimal(0)
        cost_basis = position.cost_basis if position else Decimal(0)

        try:
            action_type = ActionType(action.action_type)
        except ValueError:
            logger.warning(
                "unknown_corporate_action_type",
                action_id=action.action_id,
                action_type=action.action_type,
            )
            record = ProcessedCorporateActionRecord(
                id=str(uuid4()),
                action_id=action.action_id,
                instrument_id=action.instrument_id,
                action_type=action.action_type,
                ex_date=action.ex_date,
                status=ProcessingStatus.FAILED.value,
                error_message=f"Unknown action type: {action.action_type}",
                processed_at=datetime.now(UTC),
            )
            record = await self._repo.save(record, session=session)
            return self._to_processed_action(record)

        try:
            adjustments = compute_adjustments(action, quantity, cost_basis)
        except Exception as exc:
            logger.error(
                "corporate_action_processing_failed",
                action_id=action.action_id,
                error=str(exc),
            )
            record = ProcessedCorporateActionRecord(
                id=str(uuid4()),
                action_id=action.action_id,
                instrument_id=action.instrument_id,
                action_type=action.action_type,
                ex_date=action.ex_date,
                status=ProcessingStatus.FAILED.value,
                error_message=str(exc),
                processed_at=datetime.now(UTC),
            )
            record = await self._repo.save(record, session=session)
            return self._to_processed_action(record)

        # 3. Determine status
        status = ProcessingStatus.SKIPPED if not adjustments else ProcessingStatus.PROCESSED

        # 4. Publish trade events for splits (position changes)
        for adj in adjustments:
            if adj.quantity_delta != Decimal(0):
                side = "buy" if adj.quantity_delta > 0 else "sell"
                event = BaseEvent(
                    event_type=f"corporate_action.{action_type.value}",
                    data={
                        "portfolio_id": portfolio_id,
                        "instrument_id": adj.instrument_id,
                        "side": side,
                        "quantity": str(abs(adj.quantity_delta)),
                        "price": "0",
                        "trade_id": str(uuid4()),
                        "currency": action.currency,
                        "source": "corporate_action",
                        "action_id": action.action_id,
                    },
                    fund_slug=fund_slug,
                )
                await self._event_bus.publish(fund_topic(fund_slug, "trades.executed"), event)

            if adj.cash_amount != Decimal(0):
                event = BaseEvent(
                    event_type=f"corporate_action.{action_type.value}.cash",
                    data={
                        "portfolio_id": portfolio_id,
                        "instrument_id": adj.instrument_id,
                        "amount": str(adj.cash_amount),
                        "currency": action.currency,
                        "source": "corporate_action",
                        "action_id": action.action_id,
                    },
                    fund_slug=fund_slug,
                )
                await self._event_bus.publish(
                    fund_topic(fund_slug, "cash.settlement.created"), event
                )

        # 5. Persist record
        adjustments_json = [asdict(a) for a in adjustments] if adjustments else None
        # Convert Decimal values to strings for JSON serialization
        if adjustments_json:
            for adj_dict in adjustments_json:
                for key, value in adj_dict.items():
                    if isinstance(value, Decimal):
                        adj_dict[key] = str(value)

        record = ProcessedCorporateActionRecord(
            id=str(uuid4()),
            action_id=action.action_id,
            instrument_id=action.instrument_id,
            action_type=action.action_type,
            ex_date=action.ex_date,
            status=status.value,
            adjustments=adjustments_json,
            processed_at=datetime.now(UTC),
        )
        record = await self._repo.save(record, session=session)

        # 6. Publish processed event
        event = BaseEvent(
            event_type="corporate_actions.processed",
            data={
                "action_id": action.action_id,
                "instrument_id": action.instrument_id,
                "action_type": action.action_type,
                "status": status.value,
            },
            fund_slug=fund_slug,
        )
        await self._event_bus.publish(fund_topic(fund_slug, "corporate_actions.processed"), event)

        logger.info(
            "corporate_action_processed",
            action_id=action.action_id,
            action_type=action.action_type,
            status=status.value,
            adjustments_count=len(adjustments),
        )

        return self._to_processed_action(record)

    async def list_processed(self, *, session: AsyncSession | None = None) -> list[ProcessedAction]:
        """List all processed corporate actions."""
        records = await self._repo.list_all(session=session)
        return [self._to_processed_action(r) for r in records]

    @staticmethod
    def _to_processed_action(
        record: ProcessedCorporateActionRecord,
    ) -> ProcessedAction:
        return ProcessedAction(
            id=UUID(record.id),
            action_id=record.action_id,
            instrument_id=record.instrument_id,
            action_type=ActionType(record.action_type),
            ex_date=record.ex_date,
            status=ProcessingStatus(record.status),
            processed_at=record.processed_at,
            error_message=record.error_message,
        )
