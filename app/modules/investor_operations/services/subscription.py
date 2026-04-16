"""Subscription workflow service — orchestrates multi-party subscription lifecycle.

Each method advances the subscription request through its state machine, persists
the change, and publishes audit events.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from app.shared.schema_registry import shared_topic

from app.modules.investor_operations.core.fund_terms import (
    compute_next_dealing_date,
    validate_minimum_amount,
)
from app.modules.investor_operations.core.state_machine import apply_subscription_transition
from app.modules.investor_operations.interfaces import (
    RedemptionFrequency,
    SubscriptionRequestSummary,
    SubscriptionState,
)
from app.modules.investor_operations.models.subscription import SubscriptionRequestRecord
from app.shared.audit.events import AuditEventType
from app.shared.events import BaseEvent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.capital_accounts.services import CapitalTransactionService
    from app.modules.investor_operations.repositories.fund_terms import FundTermsRepository
    from app.modules.investor_operations.repositories.kyc import InvestorKYCRepository
    from app.modules.investor_operations.repositories.subscription import (
        SubscriptionRequestRepository,
    )
    from app.shared.events import EventBus


def _now() -> datetime:
    return datetime.now(UTC)


class SubscriptionService:
    """Orchestrates multi-party subscription workflows."""

    def __init__(
        self,
        *,
        subscription_repo: SubscriptionRequestRepository,
        fund_terms_repo: FundTermsRepository,
        kyc_repo: InvestorKYCRepository,
        capital_service: CapitalTransactionService,
        event_bus: EventBus | None = None,
    ) -> None:
        self._subscription_repo = subscription_repo
        self._terms_repo = fund_terms_repo
        self._kyc_repo = kyc_repo
        self._capital_service = capital_service
        self._event_bus = event_bus

    async def submit_subscription(
        self,
        *,
        investor_id: str,
        amount: Decimal,
        share_class: str = "default",
        session: AsyncSession | None = None,
    ) -> SubscriptionRequestSummary:
        """Create a new subscription request and move it to PENDING_KYC."""
        terms = await self._terms_repo.get_by_share_class(share_class, session=session)
        if terms and not validate_minimum_amount(amount, terms.minimum_subscription):
            msg = (
                f"Amount {amount} is below minimum subscription "
                f"{terms.minimum_subscription} for share class {share_class}"
            )
            raise ValueError(msg)

        now = _now()
        record = SubscriptionRequestRecord(
            id=str(uuid4()),
            investor_id=investor_id,
            share_class=share_class,
            requested_amount=amount,
            state=SubscriptionState.DRAFT,
            submitted_at=now,
            created_at=now,
            updated_at=now,
        )
        # Immediately transition to PENDING_KYC
        apply_subscription_transition(SubscriptionState.DRAFT, SubscriptionState.PENDING_KYC)
        record.state = SubscriptionState.PENDING_KYC

        await self._subscription_repo.save(record, session=session)

        if self._event_bus:
            await self._event_bus.publish(
                shared_topic("investor-operations"),
                BaseEvent(
                    event_type=AuditEventType.SUBSCRIPTION_SUBMITTED,
                    data={
                        "request_id": record.id,
                        "investor_id": investor_id,
                        "amount": str(amount),
                        "share_class": share_class,
                    },
                ),
            )
        return _sub_to_summary(record)

    async def record_kyc_decision(
        self,
        request_id: str,
        *,
        approved: bool,
        decision_by: str,
        notes: str = "",
        session: AsyncSession | None = None,
    ) -> SubscriptionRequestSummary:
        """Record a KYC/AML decision on a subscription request."""
        record = await self._subscription_repo.get_by_id(request_id, session=session)
        if record is None:
            msg = f"Subscription request {request_id} not found"
            raise ValueError(msg)

        current = SubscriptionState(record.state)
        target = SubscriptionState.KYC_APPROVED if approved else SubscriptionState.KYC_REJECTED
        apply_subscription_transition(current, target)

        now = _now()
        await self._subscription_repo.update_state(
            request_id,
            target,
            session=session,
            kyc_decision_at=now,
            kyc_decision_by=decision_by,
            kyc_notes=notes,
        )
        record.state = target
        record.kyc_decision_at = now
        record.kyc_decision_by = decision_by
        record.kyc_notes = notes

        if self._event_bus:
            await self._event_bus.publish(
                shared_topic("investor-operations"),
                BaseEvent(
                    event_type=AuditEventType.SUBSCRIPTION_KYC_DECIDED,
                    data={
                        "request_id": request_id,
                        "approved": approved,
                        "decision_by": decision_by,
                    },
                ),
            )
        return _sub_to_summary(record)

    async def ops_review(
        self,
        request_id: str,
        *,
        approved: bool,
        decision_by: str,
        notes: str = "",
        session: AsyncSession | None = None,
    ) -> SubscriptionRequestSummary:
        """Record ops review decision."""
        record = await self._subscription_repo.get_by_id(request_id, session=session)
        if record is None:
            msg = f"Subscription request {request_id} not found"
            raise ValueError(msg)

        current = SubscriptionState(record.state)

        if current == SubscriptionState.KYC_APPROVED:
            # First transition to PENDING_OPS_REVIEW
            apply_subscription_transition(current, SubscriptionState.PENDING_OPS_REVIEW)
            current = SubscriptionState.PENDING_OPS_REVIEW

        target = SubscriptionState.PENDING_GP_APPROVAL if approved else SubscriptionState.CANCELLED
        apply_subscription_transition(current, target)

        now = _now()
        await self._subscription_repo.update_state(
            request_id,
            target,
            session=session,
            ops_decision_at=now,
            ops_decision_by=decision_by,
            ops_notes=notes,
        )
        record.state = target
        record.ops_decision_at = now
        record.ops_decision_by = decision_by
        record.ops_notes = notes

        if self._event_bus:
            await self._event_bus.publish(
                shared_topic("investor-operations"),
                BaseEvent(
                    event_type=AuditEventType.SUBSCRIPTION_OPS_REVIEWED,
                    data={
                        "request_id": request_id,
                        "approved": approved,
                        "decision_by": decision_by,
                    },
                ),
            )
        return _sub_to_summary(record)

    async def gp_decision(
        self,
        request_id: str,
        *,
        approved: bool,
        decision_by: str,
        session: AsyncSession | None = None,
    ) -> SubscriptionRequestSummary:
        """Record GP accept/reject decision. Sets dealing_date on approval."""
        record = await self._subscription_repo.get_by_id(request_id, session=session)
        if record is None:
            msg = f"Subscription request {request_id} not found"
            raise ValueError(msg)

        current = SubscriptionState(record.state)
        target = SubscriptionState.APPROVED if approved else SubscriptionState.REJECTED
        apply_subscription_transition(current, target)

        extra: dict[str, object] = {
            "gp_decision_at": _now(),
            "gp_decision_by": decision_by,
        }

        if approved:
            terms = await self._terms_repo.get_by_share_class(record.share_class, session=session)
            if terms:
                dealing = compute_next_dealing_date(
                    RedemptionFrequency(terms.redemption_frequency),
                    terms.dealing_day,
                    date.today(),
                )
                extra["dealing_date"] = dealing
                record.dealing_date = dealing

        await self._subscription_repo.update_state(request_id, target, session=session, **extra)
        record.state = target
        record.gp_decision_at = extra["gp_decision_at"]  # type: ignore[assignment]
        record.gp_decision_by = decision_by

        if self._event_bus:
            await self._event_bus.publish(
                shared_topic("investor-operations"),
                BaseEvent(
                    event_type=AuditEventType.SUBSCRIPTION_GP_DECIDED,
                    data={
                        "request_id": request_id,
                        "approved": approved,
                        "decision_by": decision_by,
                    },
                ),
            )
        return _sub_to_summary(record)

    async def confirm_wire(
        self,
        request_id: str,
        *,
        wire_reference: str,
        session: AsyncSession | None = None,
    ) -> SubscriptionRequestSummary:
        """Confirm wire receipt, transitioning through to QUEUED_FOR_NAV."""
        record = await self._subscription_repo.get_by_id(request_id, session=session)
        if record is None:
            msg = f"Subscription request {request_id} not found"
            raise ValueError(msg)

        current = SubscriptionState(record.state)
        # Walk through intermediate states
        for intermediate in [
            SubscriptionState.PENDING_WIRE,
            SubscriptionState.WIRE_CONFIRMED,
            SubscriptionState.QUEUED_FOR_NAV,
        ]:
            apply_subscription_transition(current, intermediate)
            current = intermediate

        now = _now()
        await self._subscription_repo.update_state(
            request_id,
            SubscriptionState.QUEUED_FOR_NAV,
            session=session,
            wire_confirmed_at=now,
            wire_reference=wire_reference,
        )
        record.state = SubscriptionState.QUEUED_FOR_NAV
        record.wire_confirmed_at = now
        record.wire_reference = wire_reference

        if self._event_bus:
            await self._event_bus.publish(
                shared_topic("investor-operations"),
                BaseEvent(
                    event_type=AuditEventType.SUBSCRIPTION_WIRE_CONFIRMED,
                    data={
                        "request_id": request_id,
                        "wire_reference": wire_reference,
                    },
                ),
            )
        return _sub_to_summary(record)

    async def execute_subscriptions(
        self,
        *,
        dealing_date: date,
        nav_per_share: Decimal,
        portfolio_id: UUID,
        session: AsyncSession | None = None,
    ) -> list[SubscriptionRequestSummary]:
        """Execute all queued subscriptions for a dealing date.

        Calls the capital accounts engine to create the actual accounting entries.
        """
        if nav_per_share <= 0:
            raise ValueError(f"Cannot execute subscriptions with non-positive NAV per share: {nav_per_share}")

        records = await self._subscription_repo.list_by_dealing_date(dealing_date, session=session)
        queued = [r for r in records if r.state == SubscriptionState.QUEUED_FOR_NAV]

        results: list[SubscriptionRequestSummary] = []
        for record in queued:
            apply_subscription_transition(
                SubscriptionState(record.state), SubscriptionState.EXECUTED
            )

            shares = (record.requested_amount / nav_per_share).quantize(Decimal("0.000001"))

            await self._capital_service.process_subscription(
                investor_id=record.investor_id,
                amount=record.requested_amount,
                nav_per_share=nav_per_share,
                business_date=dealing_date,
                portfolio_id=portfolio_id,
                share_class=record.share_class,
                notes=f"Subscription request {record.id}",
                session=session,
            )

            now = _now()
            await self._subscription_repo.update_state(
                record.id,
                SubscriptionState.EXECUTED,
                session=session,
                executed_at=now,
                nav_per_share=nav_per_share,
                shares_issued=shares,
            )
            record.state = SubscriptionState.EXECUTED
            record.executed_at = now
            record.nav_per_share = nav_per_share
            record.shares_issued = shares

            if self._event_bus:
                await self._event_bus.publish(
                    shared_topic("investor-operations"),
                    BaseEvent(
                        event_type=AuditEventType.SUBSCRIPTION_EXECUTED,
                        data={
                            "request_id": record.id,
                            "investor_id": record.investor_id,
                            "amount": str(record.requested_amount),
                            "nav_per_share": str(nav_per_share),
                            "shares_issued": str(shares),
                        },
                    ),
                )
            results.append(_sub_to_summary(record))

        return results

    async def cancel_subscription(
        self,
        request_id: str,
        *,
        reason: str,
        cancelled_by: str,
        session: AsyncSession | None = None,
    ) -> SubscriptionRequestSummary:
        """Cancel a subscription request (any non-terminal state)."""
        record = await self._subscription_repo.get_by_id(request_id, session=session)
        if record is None:
            msg = f"Subscription request {request_id} not found"
            raise ValueError(msg)

        current = SubscriptionState(record.state)
        apply_subscription_transition(current, SubscriptionState.CANCELLED)

        now = _now()
        await self._subscription_repo.update_state(
            request_id,
            SubscriptionState.CANCELLED,
            session=session,
            cancelled_at=now,
            cancellation_reason=reason,
        )
        record.state = SubscriptionState.CANCELLED
        record.cancelled_at = now
        record.cancellation_reason = reason

        if self._event_bus:
            await self._event_bus.publish(
                shared_topic("investor-operations"),
                BaseEvent(
                    event_type=AuditEventType.SUBSCRIPTION_CANCELLED,
                    data={
                        "request_id": request_id,
                        "reason": reason,
                        "cancelled_by": cancelled_by,
                    },
                ),
            )
        return _sub_to_summary(record)

    async def get_subscription(
        self, request_id: str, *, session: AsyncSession | None = None
    ) -> SubscriptionRequestSummary | None:
        record = await self._subscription_repo.get_by_id(request_id, session=session)
        return _sub_to_summary(record) if record else None

    async def list_subscriptions(
        self,
        *,
        state: str | None = None,
        investor_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> list[SubscriptionRequestSummary]:
        if state:
            records = await self._subscription_repo.list_by_state(state, session=session)
        elif investor_id:
            records = await self._subscription_repo.list_by_investor(investor_id, session=session)
        else:
            # Default: list all pending states
            records = []
            for s in [
                SubscriptionState.PENDING_KYC,
                SubscriptionState.KYC_APPROVED,
                SubscriptionState.PENDING_OPS_REVIEW,
                SubscriptionState.PENDING_GP_APPROVAL,
                SubscriptionState.APPROVED,
                SubscriptionState.PENDING_WIRE,
                SubscriptionState.WIRE_CONFIRMED,
                SubscriptionState.QUEUED_FOR_NAV,
            ]:
                records.extend(await self._subscription_repo.list_by_state(s, session=session))
        return [_sub_to_summary(r) for r in records]


# ---------------------------------------------------------------------------
#  Record -> DTO converter
# ---------------------------------------------------------------------------


def _sub_to_summary(record: SubscriptionRequestRecord) -> SubscriptionRequestSummary:
    return SubscriptionRequestSummary(
        id=UUID(record.id) if isinstance(record.id, str) else record.id,
        investor_id=(
            UUID(record.investor_id) if isinstance(record.investor_id, str) else record.investor_id
        ),
        share_class=record.share_class,
        requested_amount=record.requested_amount,
        state=SubscriptionState(record.state),
        submitted_at=record.submitted_at,
        kyc_decision_at=record.kyc_decision_at,
        kyc_decision_by=record.kyc_decision_by,
        ops_decision_at=record.ops_decision_at,
        ops_decision_by=record.ops_decision_by,
        gp_decision_at=record.gp_decision_at,
        gp_decision_by=record.gp_decision_by,
        wire_confirmed_at=record.wire_confirmed_at,
        wire_reference=record.wire_reference,
        dealing_date=record.dealing_date,
        executed_at=record.executed_at,
        nav_per_share=record.nav_per_share,
        shares_issued=record.shares_issued,
        cancelled_at=record.cancelled_at,
        cancellation_reason=record.cancellation_reason,
        created_at=record.created_at,
    )
