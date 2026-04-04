"""Cash management service — balances, settlements, projections."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from app.modules.cash_management.interface import (
    CashBalance,
    CashFlowType,
    CashProjection,
    CashProjectionEntry,
    JournalEntryType,
    SettlementLadder,
    SettlementLadderEntry,
    SettlementRecord,
    SettlementStatus,
)
from app.modules.cash_management.models import (
    CashBalanceRecord,
    CashJournalRecord,
    CashSettlementRecord,
)
from app.modules.cash_management.settlement import calculate_settlement_date

if TYPE_CHECKING:
    from app.modules.cash_management.repository import (
        CashBalanceRepository,
        CashJournalRepository,
        CashProjectionRepository,
        ScheduledFlowRepository,
        SettlementRepository,
    )
    from app.modules.security_master.service import SecurityMasterService
    from app.shared.events import EventBus

logger = structlog.get_logger()

ZERO = Decimal(0)
_Q4 = Decimal("0.0001")


class CashManagementService:
    """Manages cash balances, settlements, and projections."""

    def __init__(
        self,
        *,
        balance_repo: CashBalanceRepository,
        journal_repo: CashJournalRepository,
        settlement_repo: SettlementRepository,
        scheduled_flow_repo: ScheduledFlowRepository,
        projection_repo: CashProjectionRepository,
        security_master_service: SecurityMasterService,
        event_bus: EventBus | None = None,
    ) -> None:
        self._balances = balance_repo
        self._journal = journal_repo
        self._settlements = settlement_repo
        self._scheduled = scheduled_flow_repo
        self._projections = projection_repo
        self._sm = security_master_service
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Cash balances
    # ------------------------------------------------------------------

    async def get_balances(self, portfolio_id: UUID) -> list[CashBalance]:
        records = await self._balances.get_by_portfolio(portfolio_id)
        return [
            CashBalance(
                portfolio_id=r.portfolio_id,
                currency=r.currency,
                available_balance=r.available_balance,
                pending_inflows=r.pending_inflows,
                pending_outflows=r.pending_outflows,
                total_balance=(r.available_balance + r.pending_inflows - r.pending_outflows),
                updated_at=r.updated_at,
            )
            for r in records
        ]

    async def credit(
        self,
        portfolio_id: UUID,
        currency: str,
        amount: Decimal,
        flow_type: CashFlowType,
        reference_id: str | None = None,
        description: str | None = None,
    ) -> None:
        """Credit (add) cash to a portfolio balance."""
        record = await self._balances.get_by_portfolio_currency(portfolio_id, currency)
        current_balance = record.available_balance if record else ZERO
        new_balance = current_balance + amount

        balance_record = CashBalanceRecord(
            portfolio_id=str(portfolio_id),
            currency=currency,
            available_balance=new_balance,
            pending_inflows=record.pending_inflows if record else ZERO,
            pending_outflows=record.pending_outflows if record else ZERO,
        )
        await self._balances.upsert(balance_record)

        journal = CashJournalRecord(
            portfolio_id=str(portfolio_id),
            currency=currency,
            entry_type=JournalEntryType.CREDIT,
            amount=amount,
            balance_after=new_balance,
            flow_type=flow_type,
            reference_id=reference_id,
            description=description,
        )
        await self._journal.insert(journal)

    async def debit(
        self,
        portfolio_id: UUID,
        currency: str,
        amount: Decimal,
        flow_type: CashFlowType,
        reference_id: str | None = None,
        description: str | None = None,
    ) -> None:
        """Debit (remove) cash from a portfolio balance."""
        record = await self._balances.get_by_portfolio_currency(portfolio_id, currency)
        current_balance = record.available_balance if record else ZERO
        new_balance = current_balance - amount

        balance_record = CashBalanceRecord(
            portfolio_id=str(portfolio_id),
            currency=currency,
            available_balance=new_balance,
            pending_inflows=record.pending_inflows if record else ZERO,
            pending_outflows=record.pending_outflows if record else ZERO,
        )
        await self._balances.upsert(balance_record)

        journal = CashJournalRecord(
            portfolio_id=str(portfolio_id),
            currency=currency,
            entry_type=JournalEntryType.DEBIT,
            amount=amount,
            balance_after=new_balance,
            flow_type=flow_type,
            reference_id=reference_id,
            description=description,
        )
        await self._journal.insert(journal)

    # ------------------------------------------------------------------
    # Settlements
    # ------------------------------------------------------------------

    async def create_settlement(
        self,
        portfolio_id: UUID,
        order_id: UUID | None,
        instrument_id: str,
        currency: str,
        amount: Decimal,
        trade_date: date,
        fund_slug: str | None = None,
    ) -> None:
        """Create a settlement entry for a trade."""
        # Look up country for settlement convention
        country = "US"
        try:
            instrument = await self._sm.get_by_ticker(instrument_id)
            country = getattr(instrument, "country", "US") or "US"
        except Exception:
            pass

        settlement_date = calculate_settlement_date(trade_date, country)

        record = CashSettlementRecord(
            portfolio_id=str(portfolio_id),
            order_id=str(order_id) if order_id else None,
            instrument_id=instrument_id,
            currency=currency,
            settlement_amount=amount,
            trade_date=trade_date,
            settlement_date=settlement_date,
        )
        await self._settlements.insert(record)

        # Update pending flows on the balance
        balance = await self._balances.get_by_portfolio_currency(portfolio_id, currency)
        if amount > ZERO:
            # Inflow (sell proceeds)
            new_inflows = (balance.pending_inflows if balance else ZERO) + amount
            balance_record = CashBalanceRecord(
                portfolio_id=str(portfolio_id),
                currency=currency,
                available_balance=(balance.available_balance if balance else ZERO),
                pending_inflows=new_inflows,
                pending_outflows=(balance.pending_outflows if balance else ZERO),
            )
        else:
            # Outflow (buy cost)
            new_outflows = (balance.pending_outflows if balance else ZERO) + abs(amount)
            balance_record = CashBalanceRecord(
                portfolio_id=str(portfolio_id),
                currency=currency,
                available_balance=(balance.available_balance if balance else ZERO),
                pending_inflows=(balance.pending_inflows if balance else ZERO),
                pending_outflows=new_outflows,
            )
        await self._balances.upsert(balance_record)

        await self._publish_settlement_event(
            "cash.settlement.created",
            portfolio_id,
            instrument_id,
            amount,
            settlement_date,
            fund_slug=fund_slug,
        )
        logger.info(
            "settlement_created",
            portfolio_id=str(portfolio_id),
            instrument=instrument_id,
            amount=str(amount),
            settle_date=str(settlement_date),
        )

    async def get_pending_settlements(self, portfolio_id: UUID) -> list[SettlementRecord]:
        records = await self._settlements.get_pending(portfolio_id)
        return [self._to_settlement_record(r) for r in records]

    async def process_due_settlements(self, as_of: date) -> int:
        """Settle all pending settlements due on or before as_of.

        Returns the number of settlements processed.
        """
        due = await self._settlements.get_due_settlements(as_of)
        count = 0
        for settlement in due:
            pid = UUID(settlement.portfolio_id)
            amount = settlement.settlement_amount

            if amount > ZERO:
                await self.credit(
                    pid,
                    settlement.currency,
                    amount,
                    CashFlowType.TRADE_SETTLEMENT,
                    reference_id=settlement.id,
                    description=f"Settlement: {settlement.instrument_id}",
                )
            else:
                await self.debit(
                    pid,
                    settlement.currency,
                    abs(amount),
                    CashFlowType.TRADE_SETTLEMENT,
                    reference_id=settlement.id,
                    description=f"Settlement: {settlement.instrument_id}",
                )

            await self._settlements.settle(settlement.id)
            # Note: fund_slug not available in batch context; settled events
            # are published only when fund_slug can be resolved.
            count += 1

        if count:
            logger.info("settlements_processed", count=count, as_of=str(as_of))
        return count

    # ------------------------------------------------------------------
    # Settlement ladder
    # ------------------------------------------------------------------

    async def get_settlement_ladder(
        self,
        portfolio_id: UUID,
        horizon_days: int = 10,
    ) -> SettlementLadder:
        """Build a settlement ladder showing expected flows by date."""
        today = date.today()
        end = today + timedelta(days=horizon_days)

        settlements = await self._settlements.get_by_date_range(portfolio_id, today, end)
        balances = await self._balances.get_by_portfolio(portfolio_id)

        # Start with current available balance (simplified: USD only)
        current_balance = ZERO
        for b in balances:
            current_balance += b.available_balance

        # Group by settlement date
        by_date: dict[date, tuple[Decimal, Decimal]] = {}
        for s in settlements:
            if s.status != SettlementStatus.PENDING:
                continue
            d = s.settlement_date
            inflow, outflow = by_date.get(d, (ZERO, ZERO))
            if s.settlement_amount > ZERO:
                inflow += s.settlement_amount
            else:
                outflow += abs(s.settlement_amount)
            by_date[d] = (inflow, outflow)

        entries: list[SettlementLadderEntry] = []
        cumulative = current_balance
        current = today
        while current <= end:
            inflow, outflow = by_date.get(current, (ZERO, ZERO))
            net = inflow - outflow
            cumulative += net
            if inflow > ZERO or outflow > ZERO or current == today:
                entries.append(
                    SettlementLadderEntry(
                        settlement_date=current,
                        currency="USD",
                        expected_inflow=inflow,
                        expected_outflow=outflow,
                        net_flow=net,
                        cumulative_balance=cumulative,
                    )
                )
            current += timedelta(days=1)

        return SettlementLadder(
            portfolio_id=portfolio_id,
            entries=entries,
            generated_at=datetime.now(UTC),
        )

    # ------------------------------------------------------------------
    # Cash projection
    # ------------------------------------------------------------------

    async def get_projection(
        self,
        portfolio_id: UUID,
        horizon_days: int = 30,
    ) -> CashProjection:
        """Generate a forward-looking cash projection."""
        today = date.today()
        end = today + timedelta(days=horizon_days)

        # Get pending settlements
        settlements = await self._settlements.get_by_date_range(portfolio_id, today, end)

        # Get scheduled flows
        scheduled = await self._scheduled.get_by_portfolio(portfolio_id, today, end)

        # Get current balance
        balances = await self._balances.get_by_portfolio(portfolio_id)
        current_balance = ZERO
        for b in balances:
            current_balance += b.available_balance

        # Build daily projection
        entries: list[CashProjectionEntry] = []
        running_balance = current_balance

        current = today
        while current <= end:
            opening = running_balance
            inflows = ZERO
            outflows = ZERO
            details: list[dict[str, str]] = []

            # Settlements
            for s in settlements:
                if s.settlement_date == current and s.status == "pending":
                    if s.settlement_amount > ZERO:
                        inflows += s.settlement_amount
                        details.append(
                            {
                                "type": "settlement",
                                "instrument": s.instrument_id,
                                "amount": str(s.settlement_amount),
                            }
                        )
                    else:
                        outflows += abs(s.settlement_amount)
                        details.append(
                            {
                                "type": "settlement",
                                "instrument": s.instrument_id,
                                "amount": str(s.settlement_amount),
                            }
                        )

            # Scheduled flows
            for f in scheduled:
                if f.flow_date == current:
                    if f.amount > ZERO:
                        inflows += f.amount
                    else:
                        outflows += abs(f.amount)
                    details.append(
                        {
                            "type": f.flow_type,
                            "amount": str(f.amount),
                            "description": f.description or "",
                        }
                    )

            closing = opening + inflows - outflows
            running_balance = closing

            entries.append(
                CashProjectionEntry(
                    projection_date=current,
                    currency="USD",
                    opening_balance=opening,
                    inflows=inflows,
                    outflows=outflows,
                    closing_balance=closing,
                    flow_details=details,
                )
            )
            current += timedelta(days=1)

        return CashProjection(
            portfolio_id=portfolio_id,
            base_currency="USD",
            horizon_days=horizon_days,
            entries=entries,
            projected_at=datetime.now(UTC),
        )

    # ------------------------------------------------------------------
    # Event handler — called when trades.executed fires
    # ------------------------------------------------------------------

    async def handle_trade_executed(self, event: object) -> None:
        """Create settlement entries when a trade is executed."""
        from app.shared.events import BaseEvent

        if not isinstance(event, BaseEvent):
            return

        data = event.data
        portfolio_id_str = data.get("portfolio_id")
        if not portfolio_id_str:
            return

        portfolio_id = UUID(portfolio_id_str)
        instrument_id = data.get("instrument_id", "")
        currency = data.get("currency", "USD")
        side = data.get("side", "buy")
        total_cost = Decimal(str(data.get("total_cost", "0")))

        # Buy = cash outflow (negative), Sell = cash inflow (positive)
        amount = -total_cost if side == "buy" else total_cost

        await self.create_settlement(
            portfolio_id=portfolio_id,
            order_id=UUID(data["order_id"]) if data.get("order_id") else None,
            instrument_id=instrument_id,
            currency=currency,
            amount=amount,
            trade_date=date.today(),
            fund_slug=event.fund_slug,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _publish_settlement_event(
        self,
        event_type: str,
        portfolio_id: UUID,
        instrument_id: str,
        amount: Decimal,
        settlement_date: date,
        fund_slug: str | None = None,
    ) -> None:
        """Publish a cash settlement event to Kafka."""
        if self._event_bus is None or not fund_slug:
            return
        from app.shared.events import BaseEvent
        from app.shared.schema_registry import fund_topic

        status = "created" if "created" in event_type else "settled"
        topic_base = f"cash.settlement.{status}"
        event = BaseEvent(
            event_type=event_type,
            data={
                "portfolio_id": str(portfolio_id),
                "instrument_id": instrument_id,
                "settlement_amount": str(amount),
                "settlement_date": str(settlement_date),
                "status": status,
            },
            fund_slug=fund_slug,
        )
        await self._event_bus.publish(fund_topic(fund_slug, topic_base), event)

    @staticmethod
    def _to_settlement_record(r: CashSettlementRecord) -> SettlementRecord:
        return SettlementRecord(
            id=r.id,
            portfolio_id=r.portfolio_id,
            order_id=r.order_id,
            instrument_id=r.instrument_id,
            currency=r.currency,
            settlement_amount=r.settlement_amount,
            settlement_date=r.settlement_date,
            trade_date=r.trade_date,
            status=SettlementStatus(r.status),
            created_at=r.created_at,
        )
