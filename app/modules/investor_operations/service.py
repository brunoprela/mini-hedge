"""Investor operations service — orchestrates subscription and redemption workflows.

This is the workflow layer that sits above the capital accounts "execution engine".
Each method advances the request through its state machine, persists the change,
and publishes audit events.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from app.modules.investor_operations.fund_terms import (
    compute_lock_up_expiry,
    compute_next_dealing_date,
    compute_notice_deadline,
    compute_payment_due_date,
    validate_minimum_amount,
)
from app.modules.investor_operations.gate_engine import check_gate
from app.modules.investor_operations.interface import (
    FundTermsSummary,
    GateCheckResult,
    InvestorKYCInfo,
    QueueSummary,
    RedemptionFrequency,
    RedemptionRequestSummary,
    RedemptionState,
    SubscriptionRequestSummary,
    SubscriptionState,
)
from app.modules.investor_operations.models import (
    FundTermsRecord,
    InvestorKYCRecord,
    RedemptionRequestRecord,
    SubscriptionRequestRecord,
)
from app.modules.investor_operations.state_machine import (
    apply_redemption_transition,
    apply_subscription_transition,
)
from app.shared.audit.events import AuditEventType
from app.shared.events import BaseEvent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.capital_accounts.service import CapitalAccountService
    from app.modules.investor_operations.repository import (
        FundTermsRepository,
        InvestorKYCRepository,
        RedemptionRequestRepository,
        SubscriptionRequestRepository,
    )
    from app.shared.adapters import KYCScreeningAdapter
    from app.shared.events import EventBus


def _now() -> datetime:
    return datetime.now(UTC)


class InvestorOperationsService:
    """Orchestrates multi-party subscription and redemption workflows."""

    def __init__(
        self,
        *,
        subscription_repo: SubscriptionRequestRepository,
        redemption_repo: RedemptionRequestRepository,
        fund_terms_repo: FundTermsRepository,
        kyc_repo: InvestorKYCRepository,
        capital_service: CapitalAccountService,
        kyc_adapter: KYCScreeningAdapter,
        event_bus: EventBus,
    ) -> None:
        self._subscription_repo = subscription_repo
        self._redemption_repo = redemption_repo
        self._terms_repo = fund_terms_repo
        self._kyc_repo = kyc_repo
        self._capital_service = capital_service
        self._kyc_adapter = kyc_adapter
        self._event_bus = event_bus

    # -----------------------------------------------------------------------
    #  Subscriptions
    # -----------------------------------------------------------------------

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

        await self._event_bus.publish(
            "investor_operations",
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

        await self._event_bus.publish(
            "investor_operations",
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

            await self._event_bus.publish(
                "investor_operations",
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

        return _sub_to_summary(record)

    # -----------------------------------------------------------------------
    #  Redemptions
    # -----------------------------------------------------------------------

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

        await self._event_bus.publish(
            "investor_operations",
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

            # validated → pending_gate_check → gate_applied/queued_for_nav
            if current == RedemptionState.VALIDATED:
                apply_redemption_transition(current, RedemptionState.PENDING_GATE_CHECK)
                current = RedemptionState.PENDING_GATE_CHECK

            apply_redemption_transition(current, target)
            await self._redemption_repo.update_state(rid, target, session=session, **extra)

        if result.gate_triggered:
            await self._event_bus.publish(
                "investor_operations",
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

            # Transition: QUEUED_FOR_NAV → NAV_CALCULATED → PENDING_PAYMENT
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

            await self._event_bus.publish(
                "investor_operations",
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
        """Confirm redemption payment — transitions to PAYMENT_SENT → EXECUTED."""
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

        return _red_to_summary(record)

    # -----------------------------------------------------------------------
    #  KYC
    # -----------------------------------------------------------------------

    async def screen_investor(
        self,
        *,
        investor_id: str,
        name: str,
        entity_type: str = "individual",
        tax_jurisdiction: str | None = None,
        session: AsyncSession | None = None,
    ) -> InvestorKYCInfo:
        """Trigger KYC/AML screening via the adapter and persist results."""
        result = await self._kyc_adapter.screen_investor(
            investor_id=investor_id,
            name=name,
            entity_type=entity_type,
            tax_jurisdiction=tax_jurisdiction,
        )

        # Upsert KYC record
        existing = await self._kyc_repo.get_by_investor(investor_id, session=session)
        if existing:
            existing.kyc_status = result.kyc_status
            existing.aml_status = result.aml_status
            existing.sanctions_clear = result.sanctions_clear
            existing.pep_flag = result.pep_flag
            existing.source_of_funds_verified = result.source_of_funds_verified
            existing.screening_provider = result.screening_provider
            existing.last_screened_at = _now()
            existing.notes = result.notes
            await self._kyc_repo.upsert(existing, session=session)
            record = existing
        else:
            record = InvestorKYCRecord(
                investor_id=investor_id,
                kyc_status=result.kyc_status,
                aml_status=result.aml_status,
                sanctions_clear=result.sanctions_clear,
                pep_flag=result.pep_flag,
                source_of_funds_verified=result.source_of_funds_verified,
                screening_provider=result.screening_provider,
                last_screened_at=_now(),
                notes=result.notes,
            )
            await self._kyc_repo.upsert(record, session=session)

        return InvestorKYCInfo(
            investor_id=UUID(investor_id),
            kyc_status=result.kyc_status,
            aml_status=result.aml_status,
            sanctions_clear=result.sanctions_clear,
            pep_flag=result.pep_flag,
            source_of_funds_verified=result.source_of_funds_verified,
            accredited_investor=bool(getattr(record, "accredited_investor", False)),
            last_screened_at=record.last_screened_at,
            screening_expires_at=record.screening_expires_at,
            screening_provider=result.screening_provider,
        )

    async def get_investor_kyc(
        self,
        investor_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> InvestorKYCInfo | None:
        """Get the current KYC status for an investor."""
        record = await self._kyc_repo.get_by_investor(investor_id, session=session)
        if record is None:
            return None
        return InvestorKYCInfo(
            investor_id=UUID(record.investor_id),
            kyc_status=record.kyc_status,
            aml_status=record.aml_status,
            sanctions_clear=record.sanctions_clear,
            pep_flag=record.pep_flag,
            source_of_funds_verified=record.source_of_funds_verified,
            accredited_investor=record.accredited_investor,
            last_screened_at=record.last_screened_at,
            screening_expires_at=record.screening_expires_at,
            screening_provider=record.screening_provider,
        )

    # -----------------------------------------------------------------------
    #  Fund Terms
    # -----------------------------------------------------------------------

    async def get_fund_terms(
        self,
        share_class: str = "default",
        *,
        session: AsyncSession | None = None,
    ) -> FundTermsSummary | None:
        record = await self._terms_repo.get_by_share_class(share_class, session=session)
        if record is None:
            return None
        return _terms_to_summary(record)

    async def list_fund_terms(
        self, *, session: AsyncSession | None = None
    ) -> list[FundTermsSummary]:
        records = await self._terms_repo.get_all_active(session=session)
        return [_terms_to_summary(r) for r in records]

    async def upsert_fund_terms(
        self,
        *,
        share_class: str,
        lock_up_months: int = 12,
        notice_period_days: int = 45,
        redemption_frequency: str = "quarterly",
        gate_pct: Decimal = Decimal("0.25"),
        minimum_subscription: Decimal = Decimal("1000000"),
        minimum_redemption: Decimal = Decimal("100000"),
        dealing_day: int = -1,
        payment_days: int = 30,
        session: AsyncSession | None = None,
    ) -> FundTermsSummary:
        existing = await self._terms_repo.get_by_share_class(share_class, session=session)
        if existing:
            existing.lock_up_months = lock_up_months
            existing.notice_period_days = notice_period_days
            existing.redemption_frequency = redemption_frequency
            existing.gate_pct = gate_pct
            existing.minimum_subscription = minimum_subscription
            existing.minimum_redemption = minimum_redemption
            existing.dealing_day = dealing_day
            existing.payment_days = payment_days
            await self._terms_repo.upsert(existing, session=session)
            return _terms_to_summary(existing)

        record = FundTermsRecord(
            share_class=share_class,
            lock_up_months=lock_up_months,
            notice_period_days=notice_period_days,
            redemption_frequency=redemption_frequency,
            gate_pct=gate_pct,
            minimum_subscription=minimum_subscription,
            minimum_redemption=minimum_redemption,
            dealing_day=dealing_day,
            payment_days=payment_days,
        )
        await self._terms_repo.upsert(record, session=session)
        return _terms_to_summary(record)

    # -----------------------------------------------------------------------
    #  Query helpers
    # -----------------------------------------------------------------------

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
        sub_counts = await self._subscription_repo.count_by_state(session=session)
        red_counts = await self._redemption_repo.count_by_state(session=session)

        pending_sub_states = {
            SubscriptionState.PENDING_KYC,
            SubscriptionState.KYC_APPROVED,
            SubscriptionState.PENDING_OPS_REVIEW,
            SubscriptionState.PENDING_GP_APPROVAL,
            SubscriptionState.APPROVED,
            SubscriptionState.PENDING_WIRE,
            SubscriptionState.WIRE_CONFIRMED,
            SubscriptionState.QUEUED_FOR_NAV,
        }
        pending_red_states = {
            RedemptionState.PENDING_VALIDATION,
            RedemptionState.VALIDATED,
            RedemptionState.PENDING_GATE_CHECK,
            RedemptionState.GATE_APPLIED,
            RedemptionState.QUEUED_FOR_NAV,
            RedemptionState.NAV_CALCULATED,
            RedemptionState.PENDING_PAYMENT,
        }

        pending_subs = sum(v for k, v in sub_counts.items() if k in pending_sub_states)
        pending_reds = sum(v for k, v in red_counts.items() if k in pending_red_states)

        # Get total amounts from pending subscriptions/redemptions
        sub_records = await self.list_subscriptions(session=session)
        red_records = await self.list_redemptions(session=session)

        total_sub = sum(r.requested_amount for r in sub_records)
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
            pending_subscriptions=pending_subs,
            pending_redemptions=pending_reds,
            total_subscription_amount=total_sub,
            total_redemption_amount=total_red,
            next_dealing_date=next_dealing,
        )


# ---------------------------------------------------------------------------
#  Record → DTO converters
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


def _terms_to_summary(record: FundTermsRecord) -> FundTermsSummary:
    return FundTermsSummary(
        id=UUID(record.id) if isinstance(record.id, str) else record.id,
        share_class=record.share_class,
        lock_up_months=record.lock_up_months,
        notice_period_days=record.notice_period_days,
        redemption_frequency=RedemptionFrequency(record.redemption_frequency),
        gate_pct=record.gate_pct,
        minimum_subscription=record.minimum_subscription,
        minimum_redemption=record.minimum_redemption,
        dealing_day=record.dealing_day,
        payment_days=record.payment_days,
        is_active=record.is_active,
    )
