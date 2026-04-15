"""Position reconciliation — three-way match: internal vs broker vs fund admin.

The reconciler compares positions across three independent sources:
  1. Internal positions (platform database)
  2. Broker/prime broker statement (mock-exchange execution engine)
  3. Fund administrator statement (mock-exchange fund admin service)

For mock-exchange, both external sources are HTTP calls. In production,
the broker file would be a CSV/FIX file from the prime broker and the
admin file would come from the fund administrator (Citco, SS&C, etc.).

Cash reconciliation compares internal cash balances against the fund
administrator's independently computed cash.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from app.modules.eod.interfaces.reconciliation import (
    BreakType,
    CashBreak,
    ReconciliationBreak,
    ReconciliationResult,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.cash_management.services import CashManagementService
    from app.modules.eod.core.auto_resolver import BreakAutoResolver
    from app.modules.eod.repositories import ReconciliationBreakRepository, ReconciliationRepository
    from app.modules.positions.services import PositionService
    from app.shared.adapters.broker import BrokerAdapter
    from app.shared.adapters.fund_admin import FundAdminAdapter

logger = structlog.get_logger()

ZERO = Decimal(0)
MATERIAL_THRESHOLD = Decimal("0.01")
CASH_MATERIAL_THRESHOLD = Decimal("1.00")


class PositionReconciler:
    """Three-way position and cash reconciliation."""

    def __init__(
        self,
        *,
        position_service: PositionService,
        broker_adapter: BrokerAdapter,
        recon_repo: ReconciliationRepository,
        break_repo: ReconciliationBreakRepository | None = None,
        fund_admin_adapter: FundAdminAdapter | None = None,
        cash_service: CashManagementService | None = None,
        auto_resolver: BreakAutoResolver | None = None,
    ) -> None:
        self._positions = position_service
        self._broker = broker_adapter
        self._recon_repo = recon_repo
        self._break_repo = break_repo
        self._admin = fund_admin_adapter
        self._cash = cash_service
        self._auto_resolver = auto_resolver

    async def reconcile(
        self,
        portfolio_id: UUID,
        business_date: date,
        *,
        session: AsyncSession | None = None,
    ) -> ReconciliationResult:
        """Run three-way position reconciliation + cash reconciliation."""
        # 1. Gather all three position views
        internal_positions = await self._positions.get_by_portfolio(portfolio_id, session=session)
        internal_map = {p.instrument_id: p.quantity for p in internal_positions}
        broker_map = await self._broker.get_eod_positions(str(portfolio_id), business_date)

        admin_map: dict[str, Decimal] | None = None
        if self._admin is not None:
            try:
                admin_map = await self._admin.get_positions()
            except Exception:
                logger.warning("admin_positions_unavailable")

        # 2. Three-way position matching
        breaks = self._match_positions(internal_map, broker_map, admin_map)

        # 3. Cash reconciliation
        cash_breaks = await self._reconcile_cash(portfolio_id, session=session)

        all_instruments = set(internal_map) | set(broker_map) | set(admin_map or {})
        is_clean = len(breaks) == 0 and len(cash_breaks) == 0

        # Persist summary
        await self._recon_repo.upsert(
            portfolio_id=str(portfolio_id),
            business_date=business_date,
            total_positions=len(all_instruments),
            matched_positions=len(all_instruments) - len(breaks),
            is_clean=is_clean,
            breaks=[b.model_dump(mode="json") for b in breaks],
            session=session,
        )

        # Persist individual break records for resolution tracking
        if self._break_repo and (breaks or cash_breaks):
            await self._persist_breaks(
                portfolio_id, business_date, breaks, cash_breaks, session=session
            )

        # Run auto-resolution rules if configured
        if self._auto_resolver is not None and self._break_repo is not None:
            auto_result = await self._auto_resolver.process_breaks(
                str(portfolio_id), business_date, session=session
            )
            logger.info(
                "auto_resolution_after_recon",
                portfolio_id=str(portfolio_id),
                auto_resolved=auto_result.auto_resolved,
                auto_escalated=auto_result.auto_escalated,
            )

        result = ReconciliationResult(
            portfolio_id=portfolio_id,
            business_date=business_date,
            total_positions=len(all_instruments),
            matched_positions=len(all_instruments) - len(breaks),
            breaks=breaks,
            cash_breaks=cash_breaks,
            is_clean=is_clean,
            reconciled_at=datetime.now(UTC),
        )

        logger.info(
            "position_reconciliation_complete",
            portfolio_id=str(portfolio_id),
            business_date=str(business_date),
            total=result.total_positions,
            position_breaks=len(breaks),
            cash_breaks=len(cash_breaks),
            three_way=admin_map is not None,
        )
        return result

    def _match_positions(
        self,
        internal: dict[str, Decimal],
        broker: dict[str, Decimal],
        admin: dict[str, Decimal] | None,
    ) -> list[ReconciliationBreak]:
        """Compare positions across all available sources."""
        all_instruments = set(internal) | set(broker) | set(admin or {})
        breaks: list[ReconciliationBreak] = []

        for iid in all_instruments:
            int_qty = internal.get(iid, ZERO)
            brk_qty = broker.get(iid, ZERO)
            adm_qty = admin.get(iid, ZERO) if admin is not None else None

            # Internal vs broker
            if int_qty == ZERO and brk_qty != ZERO:
                breaks.append(
                    self._break(
                        iid,
                        BreakType.MISSING_INTERNAL,
                        int_qty,
                        brk_qty,
                        adm_qty,
                    )
                )
            elif brk_qty == ZERO and int_qty != ZERO:
                breaks.append(
                    self._break(
                        iid,
                        BreakType.MISSING_BROKER,
                        int_qty,
                        brk_qty,
                        adm_qty,
                    )
                )
            elif int_qty != brk_qty:
                breaks.append(
                    self._break(
                        iid,
                        BreakType.QUANTITY_MISMATCH,
                        int_qty,
                        brk_qty,
                        adm_qty,
                    )
                )
            elif admin is not None:
                # Internal and broker agree — check admin
                if adm_qty is None:
                    raise ValueError(f"Admin position for {iid} has no quantity")
                if adm_qty == ZERO and int_qty != ZERO:
                    breaks.append(
                        self._break(
                            iid,
                            BreakType.MISSING_ADMIN,
                            int_qty,
                            brk_qty,
                            adm_qty,
                        )
                    )
                elif adm_qty != int_qty:
                    breaks.append(
                        self._break(
                            iid,
                            BreakType.INTERNAL_ADMIN_MISMATCH,
                            int_qty,
                            brk_qty,
                            adm_qty,
                        )
                    )

            # Broker vs admin (when both disagree but we haven't flagged yet)
            if (
                admin is not None
                and adm_qty is not None
                and brk_qty != adm_qty
                and int_qty == brk_qty
                and int_qty != ZERO
            ):
                # Already caught above as INTERNAL_ADMIN_MISMATCH or
                # MISSING_ADMIN, so skip to avoid duplicates
                pass
            elif (
                admin is not None
                and adm_qty is not None
                and brk_qty != adm_qty
                and int_qty != brk_qty
                and brk_qty != ZERO
                and adm_qty != ZERO
            ):
                # All three disagree — the QUANTITY_MISMATCH above covers
                # internal vs broker; add broker vs admin break
                breaks.append(
                    ReconciliationBreak(
                        instrument_id=iid,
                        break_type=BreakType.BROKER_ADMIN_MISMATCH,
                        internal_quantity=int_qty,
                        broker_quantity=brk_qty,
                        admin_quantity=adm_qty,
                        difference=brk_qty - adm_qty,
                        is_material=abs(brk_qty - adm_qty) > MATERIAL_THRESHOLD,
                    )
                )

        return breaks

    def _break(
        self,
        iid: str,
        break_type: BreakType,
        int_qty: Decimal,
        brk_qty: Decimal,
        adm_qty: Decimal | None,
    ) -> ReconciliationBreak:
        diff = int_qty - brk_qty
        return ReconciliationBreak(
            instrument_id=iid,
            break_type=break_type,
            internal_quantity=int_qty,
            broker_quantity=brk_qty,
            admin_quantity=adm_qty,
            difference=diff,
            is_material=abs(diff) > MATERIAL_THRESHOLD,
        )

    async def _reconcile_cash(
        self,
        portfolio_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> list[CashBreak]:
        """Compare internal cash balances against the admin's cash view."""
        if self._admin is None or self._cash is None:
            return []

        try:
            admin_cash = await self._admin.get_cash_balances()
        except Exception:
            logger.warning("admin_cash_unavailable")
            return []

        internal_balances = await self._cash.get_balances(portfolio_id, session=session)
        internal_cash: dict[str, Decimal] = {}
        for b in internal_balances:
            internal_cash[b.currency] = internal_cash.get(b.currency, ZERO) + b.total_balance

        all_currencies = set(internal_cash) | set(admin_cash)
        breaks: list[CashBreak] = []

        for ccy in all_currencies:
            int_bal = internal_cash.get(ccy, ZERO)
            adm_bal = admin_cash.get(ccy, ZERO)
            diff = int_bal - adm_bal
            if abs(diff) > CASH_MATERIAL_THRESHOLD:
                breaks.append(
                    CashBreak(
                        currency=ccy,
                        internal_balance=int_bal,
                        admin_balance=adm_bal,
                        difference=diff,
                        is_material=True,
                    )
                )

        return breaks

    async def _persist_breaks(
        self,
        portfolio_id: UUID,
        business_date: date,
        position_breaks: list[ReconciliationBreak],
        cash_breaks: list[CashBreak],
        *,
        session: AsyncSession | None = None,
    ) -> None:
        """Persist individual break records for tracking and resolution."""
        from app.modules.eod.models import ReconciliationBreakRecord

        if self._break_repo is None:
            raise RuntimeError("Break repository not configured — cannot persist breaks")

        records: list[ReconciliationBreakRecord] = []

        for b in position_breaks:
            records.append(
                ReconciliationBreakRecord(
                    id=str(uuid4()),
                    portfolio_id=str(portfolio_id),
                    business_date=business_date,
                    instrument_id=b.instrument_id,
                    break_type=b.break_type.value,
                    internal_quantity=b.internal_quantity,
                    broker_quantity=b.broker_quantity,
                    admin_quantity=b.admin_quantity,
                    difference=b.difference,
                    is_material=b.is_material,
                )
            )

        for cb in cash_breaks:
            records.append(
                ReconciliationBreakRecord(
                    id=str(uuid4()),
                    portfolio_id=str(portfolio_id),
                    business_date=business_date,
                    break_type=BreakType.CASH_MISMATCH.value,
                    internal_quantity=ZERO,
                    broker_quantity=ZERO,
                    difference=cb.difference,
                    is_material=cb.is_material,
                    currency=cb.currency,
                    internal_balance=cb.internal_balance,
                    admin_balance=cb.admin_balance,
                )
            )

        if records:
            await self._break_repo.create_many(records, session=session)
