"""Redemption workflow service — orchestrates redemption lifecycle and gating.

Each method advances the redemption request through its state machine, persists
the change, and publishes audit events.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from app.shared.schema_registry import shared_topic

from app.modules.investor_operations.core.fund_terms import (
    compute_lock_up_expiry,
    compute_next_dealing_date,
    compute_notice_deadline,
    compute_payment_due_date,
    validate_minimum_amount,
)
from app.modules.investor_operations.core.gate_engine import check_gate
from app.modules.investor_operations.core.state_machine import apply_redemption_transition
from app.modules.investor_operations.interfaces import (
    GateCheckResult,
    QueueSummary,
    RedemptionFrequency,
    RedemptionRequestSummary,
    RedemptionState,
)
from app.modules.investor_operations.models.redemption import RedemptionRequestRecord
from app.shared.audit.events import AuditEventType
from app.shared.events import BaseEvent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.capital_accounts.services import CapitalTransactionService
    from app.modules.investor_operations.repositories.fund_terms import FundTermsRepository
    from app.modules.investor_operations.repositories.redemption import (
        RedemptionRequestRepository,
    )
    from app.shared.events import EventBus


def _now() -> datetime:
    return datetime.now(UTC)


class RedemptionService:
    """Orchestrates redemption workflows including gate checks."""

    def __init__(
        self,
        *,
        redemption_repo: RedemptionRequestRepository,
        fund_terms_repo: FundTermsRepository,
        capital_service: CapitalTransactionService,
        event_bus: EventBus | None = None,
    ) -> None:
        self._redemption_repo = redemption_repo
        self._terms_repo = fund_terms_repo
        self._capital_service = capital_service
        self._event_bus = event_bus

    async def submit_redemption(
        self,
        *,
        investor_id: str,
        amount: Decimal,
        notice_date: date | None = None,
        session: AsyncSession | None = None,
    ) -> RedemptionRequestSummary:
        """Create a new redemption request and move it to PENDING_VALIDATION."""
        if notice_date is None:
            notice_date = date.today()

        now = _now()
        record = RedemptionRequestRecord(
            id=str(uuid4()),
            investor_id=investor_id,
            requested_amount=amount,
            state=RedemptionState.DRAFT,
            notice_date=notice_date,
            submitted_at=now,
            created_at=now,
            updated_at=now,
            gate_applied=False,
        )
        apply_redemption_transition(RedemptionState.DRAFT, RedemptionState.PENDING_VALIDATION)
        record.state = RedemptionState.PENDING_VALIDATION

        await self._redemption_repo.save(record, session=session)

        if self._event_bus:
            await self._event_bus.publish(
                shared_topic("investor-operations"),
                BaseEvent(
                    event_type=AuditEventType.REDEMPTION_SUBMITTED,
                    data={
                        "request_id": record.id,
                        "investor_id": investor_id,
                        "amount": str(amount),
                        "notice_date": notice_date.isoformat(),
                    },
                ),
            )
        return _red_to_summary(record)

    async def validate_redemption(
        self,
        request_id: str,
        *,
        share_class: str = "default",
        subscription_date: date | None = None,
        session: AsyncSession | None = None,
    ) -> RedemptionRequestSummary:
        """Validate lock-up, notice period, and minimum amount against fund terms."""
        record = await self._redemption_repo.get_by_id(request_id, session=session)
        if record is None:
            msg = f"Redemption request {request_id} not found"
            raise ValueError(msg)

        current = RedemptionState(record.state)
        terms = await self._terms_repo.get_by_share_class(share_class, session=session)

        failed_reason: str | None = None
        extra: dict[str, object] = {}

        if terms:
            # Check minimum redemption
            if not validate_minimum_amount(record.requested_amount, terms.minimum_redemption):
                failed_reason = (
                    f"Amount {record.requested_amount} below minimum {terms.minimum_redemption}"
                )

            # Check lock-up
            if subscription_date and not failed_reason:
                expiry = compute_lock_up_expiry(subscription_date, terms.lock_up_months)
                if date.today() < expiry:
                    failed_reason = (
                        f"Lock-up expires {expiry.isoformat()}, cannot redeem until then"
                    )
                extra["lock_up_expiry_date"] = expiry

            # Compute earliest redemption date from notice period
            earliest = compute_notice_deadline(record.notice_date, terms.notice_period_days)
            extra["earliest_redemption_date"] = earliest

        if failed_reason:
            target = RedemptionState.VALIDATION_FAILED
            apply_redemption_transition(current, target)
            extra["cancellation_reason"] = failed_reason
        else:
            target = RedemptionState.VALIDATED
            apply_redemption_transition(current, target)

        await self._redemption_repo.update_state(request_id, target, session=session, **extra)
        record.state = target
        if "earliest_redemption_date" in extra:
            record.earliest_redemption_date = extra["earliest_redemption_date"]  # type: ignore[assignment]
        if "lock_up_expiry_date" in extra:
            record.lock_up_expiry_date = extra["lock_up_expiry_date"]  # type: ignore[assignment]

        if self._event_bus:
            await self._event_bus.publish(
                shared_topic("investor-operations"),
                BaseEvent(
                    event_type=AuditEventType.REDEMPTION_VALIDATED,
                    data={
                        "request_id": request_id,
                        "validated": target == RedemptionState.VALIDATED,
                        "reason": failed_reason or "",
                    },
                ),
            )
        return _red_to_summary(record)

    async def run_gate_check(
        self,
        *,
        dealing_date: date,
        fund_nav: Decimal,
        gate_pct: Decimal | None = None,
        share_class: str = "default",
        session: AsyncSession | None = None,
    ) -> GateCheckResult:
        """Run the fund-level gate check on all pending redemptions."""
        if gate_pct is None:
            terms = await self._terms_repo.get_by_share_class(share_class, session=session)
            gate_pct = terms.gate_pct if terms else Decimal("0.25")

        pending = await self._redemption_repo.list_pending_for_gate(session=session)
        requests = [(r.id, r.requested_amount) for r in pending]

        result = check_gate(requests, fund_nav, gate_pct)

        for alloc in result.allocations:
            rid = str(alloc.request_id)
            if result.gate_triggered:
                target = RedemptionState.GATE_APPLIED
                extra: dict[str, object] = {
                    "gate_applied": True,
                    "gate_pct": gate_pct,
                    "approved_amount": alloc.approved_amount,
                    "dealing_date": dealing_date,
                }
            else:
                target = RedemptionState.QUEUED_FOR_NAV
                extra = {
                    "approved_amount": alloc.approved_amount,
                    "dealing_date": dealing_date,
                }

            record = next(r for r in pending if r.id == rid)
            current = RedemptionState(record.state)

            # validated -> pending_gate_check -> gate_applied/queued_for_nav
            if current == RedemptionState.VALIDATED:
                apply_redemption_transition(current, RedemptionState.PENDING_GATE_CHECK)
                current = RedemptionState.PENDING_GATE_CHECK

            apply_redemption_transition(current, target)
            await self._redemption_repo.update_state(rid, target, session=session, **extra)

        if result.gate_triggered and self._event_bus:
            await self._event_bus.publish(
                shared_topic("investor-operations"),
                BaseEvent(
                    event_type=AuditEventType.REDEMPTION_GATE_APPLIED,
                    data={
                        "dealing_date": dealing_date.isoformat(),
                        "total_requested": str(result.total_requested),
                        "total_approved": str(result.total_approved),
                        "gate_capacity": str(result.gate_capacity),
                    },
                ),
            )

        return result

    async def execute_redemptions(
        self,
        *,
        dealing_date: date,
        nav_per_share: Decimal,
        portfolio_id: UUID,
        session: AsyncSession | None = None,
    ) -> list[RedemptionRequestSummary]:
        """Execute all queued redemptions for a dealing date."""
        if nav_per_share <= 0:
            raise ValueError(f"Cannot execute redemptions with non-positive NAV per share: {nav_per_share}")

        records = await self._redemption_repo.list_by_dealing_date(dealing_date, session=session)
        queued = [
            r
            for r in records
            if r.state in (RedemptionState.QUEUED_FOR_NAV, RedemptionState.GATE_APPLIED)
        ]

        # Gate-applied requests need to transition through QUEUED_FOR_NAV first
        for record in queued:
            current = RedemptionState(record.state)
            if current == RedemptionState.GATE_APPLIED:
                apply_redemption_transition(current, RedemptionState.QUEUED_FOR_NAV)
                await self._redemption_repo.update_state(
                    record.id,
                    RedemptionState.QUEUED_FOR_NAV,
                    session=session,
                )
                record.state = RedemptionState.QUEUED_FOR_NAV

        # Look up fund terms for payment_days
        terms = await self._terms_repo.get_by_share_class("default", session=session)
        payment_days = terms.payment_days if terms else 30

        results: list[RedemptionRequestSummary] = []
        for record in queued:
            redemption_amount = record.approved_amount or record.requested_amount
            shares = (redemption_amount / nav_per_share).quantize(Decimal("0.000001"))

            # Transition: QUEUED_FOR_NAV -> NAV_CALCULATED -> PENDING_PAYMENT
            apply_redemption_transition(
                RedemptionState.QUEUED_FOR_NAV, RedemptionState.NAV_CALCULATED
            )
            apply_redemption_transition(
                RedemptionState.NAV_CALCULATED, RedemptionState.PENDING_PAYMENT
            )

            await self._capital_service.process_redemption(
                investor_id=record.investor_id,
                amount=redemption_amount,
                nav_per_share=nav_per_share,
                business_date=dealing_date,
                portfolio_id=portfolio_id,
                notes=f"Redemption request {record.id}",
                session=session,
            )

            payment_due = compute_payment_due_date(dealing_date, payment_days)
            await self._redemption_repo.update_state(
                record.id,
                RedemptionState.PENDING_PAYMENT,
                session=session,
                nav_per_share=nav_per_share,
                shares_redeemed=shares,
                payment_due_date=payment_due,
            )
            record.state = RedemptionState.PENDING_PAYMENT
            record.nav_per_share = nav_per_share
            record.shares_redeemed = shares
            record.payment_due_date = payment_due

            if self._event_bus:
                await self._event_bus.publish(
                    shared_topic("investor-operations"),
                    BaseEvent(
                        event_type=AuditEventType.REDEMPTION_EXECUTED,
                        data={
                            "request_id": record.id,
                            "investor_id": record.investor_id,
                            "amount": str(redemption_amount),
                            "nav_per_share": str(nav_per_share),
                            "shares_redeemed": str(shares),
                        },
                    ),
                )
            results.append(_red_to_summary(record))

        return results

    async def confirm_payment(
        self,
        request_id: str,
        *,
        payment_reference: str,
        session: AsyncSession | None = None,
    ) -> RedemptionRequestSummary:
        """Confirm redemption payment -- transitions to PAYMENT_SENT -> EXECUTED."""
        record = await self._redemption_repo.get_by_id(request_id, session=session)
        if record is None:
            msg = f"Redemption request {request_id} not found"
            raise ValueError(msg)

        current = RedemptionState(record.state)
        apply_redemption_transition(current, RedemptionState.PAYMENT_SENT)
        apply_redemption_transition(RedemptionState.PAYMENT_SENT, RedemptionState.EXECUTED)

        now = _now()
        await self._redemption_repo.update_state(
            request_id,
            RedemptionState.EXECUTED,
            session=session,
            payment_sent_at=now,
            payment_reference=payment_reference,
        )
        record.state = RedemptionState.EXECUTED
        record.payment_sent_at = now
        record.payment_reference = payment_reference

        if self._event_bus:
            await self._event_bus.publish(
                shared_topic("investor-operations"),
                BaseEvent(
                    event_type=AuditEventType.REDEMPTION_PAYMENT_CONFIRMED,
                    data={
                        "request_id": request_id,
                        "payment_reference": payment_reference,
                    },
                ),
            )
        return _red_to_summary(record)

    async def cancel_redemption(
        self,
        request_id: str,
        *,
        reason: str,
        cancelled_by: str,
        session: AsyncSession | None = None,
    ) -> RedemptionRequestSummary:
        """Cancel a redemption request (any non-terminal state)."""
        record = await self._redemption_repo.get_by_id(request_id, session=session)
        if record is None:
            msg = f"Redemption request {request_id} not found"
            raise ValueError(msg)

        current = RedemptionState(record.state)
        apply_redemption_transition(current, RedemptionState.CANCELLED)

        now = _now()
        await self._redemption_repo.update_state(
            request_id,
            RedemptionState.CANCELLED,
            session=session,
            cancelled_at=now,
            cancellation_reason=reason,
        )
        record.state = RedemptionState.CANCELLED
        record.cancelled_at = now
        record.cancellation_reason = reason

        if self._event_bus:
            await self._event_bus.publish(
                shared_topic("investor-operations"),
                BaseEvent(
                    event_type=AuditEventType.REDEMPTION_CANCELLED,
                    data={
                        "request_id": request_id,
                        "reason": reason,
                        "cancelled_by": cancelled_by,
                    },
                ),
            )
        return _red_to_summary(record)

    async def get_redemption(
        self, request_id: str, *, session: AsyncSession | None = None
    ) -> RedemptionRequestSummary | None:
        record = await self._redemption_repo.get_by_id(request_id, session=session)
        return _red_to_summary(record) if record else None

    async def list_redemptions(
        self,
        *,
        state: str | None = None,
        investor_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> list[RedemptionRequestSummary]:
        if state:
            records = await self._redemption_repo.list_by_state(state, session=session)
        elif investor_id:
            records = await self._redemption_repo.list_by_investor(investor_id, session=session)
        else:
            records = []
            for s in [
                RedemptionState.PENDING_VALIDATION,
                RedemptionState.VALIDATED,
                RedemptionState.PENDING_GATE_CHECK,
                RedemptionState.GATE_APPLIED,
                RedemptionState.QUEUED_FOR_NAV,
                RedemptionState.NAV_CALCULATED,
                RedemptionState.PENDING_PAYMENT,
            ]:
                records.extend(await self._redemption_repo.list_by_state(s, session=session))
        return [_red_to_summary(r) for r in records]

    async def get_queue_summary(
        self,
        *,
        share_class: str = "default",
        session: AsyncSession | None = None,
    ) -> QueueSummary:
        """Summary of pending subscription/redemption counts and amounts."""
        # NOTE: This method only has access to redemption data.
        # Subscription counts come from the redemption repo's count_by_state
        # which returns redemption state counts.
        red_counts = await self._redemption_repo.count_by_state(session=session)

        pending_red_states = {
            RedemptionState.PENDING_VALIDATION,
            RedemptionState.VALIDATED,
            RedemptionState.PENDING_GATE_CHECK,
            RedemptionState.GATE_APPLIED,
            RedemptionState.QUEUED_FOR_NAV,
            RedemptionState.NAV_CALCULATED,
            RedemptionState.PENDING_PAYMENT,
        }

        pending_reds = sum(v for k, v in red_counts.items() if k in pending_red_states)

        # Get total amounts from pending redemptions
        red_records = await self.list_redemptions(session=session)
        total_red = sum(r.requested_amount for r in red_records)

        # Next dealing date
        terms = await self._terms_repo.get_by_share_class(share_class, session=session)
        next_dealing: date | None = None
        if terms:
            next_dealing = compute_next_dealing_date(
                RedemptionFrequency(terms.redemption_frequency),
                terms.dealing_day,
                date.today(),
            )

        return QueueSummary(
            pending_subscriptions=0,
            pending_redemptions=pending_reds,
            total_subscription_amount=Decimal(0),
            total_redemption_amount=total_red,
            next_dealing_date=next_dealing,
        )


# ---------------------------------------------------------------------------
#  Record -> DTO converter
# ---------------------------------------------------------------------------


def _red_to_summary(record: RedemptionRequestRecord) -> RedemptionRequestSummary:
    return RedemptionRequestSummary(
        id=UUID(record.id) if isinstance(record.id, str) else record.id,
        investor_id=(
            UUID(record.investor_id) if isinstance(record.investor_id, str) else record.investor_id
        ),
        requested_amount=record.requested_amount,
        approved_amount=record.approved_amount,
        state=RedemptionState(record.state),
        submitted_at=record.submitted_at,
        notice_date=record.notice_date,
        earliest_redemption_date=record.earliest_redemption_date,
        lock_up_expiry_date=record.lock_up_expiry_date,
        gate_applied=record.gate_applied,
        gate_pct=record.gate_pct,
        dealing_date=record.dealing_date,
        nav_per_share=record.nav_per_share,
        shares_redeemed=record.shares_redeemed,
        payment_due_date=record.payment_due_date,
        payment_sent_at=record.payment_sent_at,
        payment_reference=record.payment_reference,
        cancelled_at=record.cancelled_at,
        cancellation_reason=record.cancellation_reason,
        created_at=record.created_at,
    )
