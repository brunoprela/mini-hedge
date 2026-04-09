"""Capital accounts service — orchestrates allocation, subscriptions, and queries."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from app.modules.capital_accounts.calculator import (
    allocate_fees,
    allocate_pnl,
    compute_subscription_shares,
    recompute_ownership,
)
from app.modules.capital_accounts.interface import (
    CapitalAccountSummary,
    CapitalTransaction,
    FundCapitalOverview,
    InvestorEntityType,
    InvestorInfo,
    TransactionType,
)
from app.modules.capital_accounts.models import (
    CapitalAccountRecord,
    CapitalTransactionRecord,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.capital_accounts.repository import (
        CapitalAccountRepository,
        CapitalTransactionRepository,
        InvestorRepository,
    )
    from app.modules.cash_management.service import CashManagementService

logger = structlog.get_logger()

ZERO = Decimal(0)


class CapitalAccountService:
    """Manages investor capital accounts within a fund."""

    def __init__(
        self,
        *,
        investor_repo: InvestorRepository,
        account_repo: CapitalAccountRepository,
        transaction_repo: CapitalTransactionRepository,
        cash_service: CashManagementService | None = None,
    ) -> None:
        self._investor_repo = investor_repo
        self._account_repo = account_repo
        self._transaction_repo = transaction_repo
        self._cash_service = cash_service

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def list_investors(self, *, session: AsyncSession | None = None) -> list[InvestorInfo]:
        records = await self._investor_repo.get_all_active(session=session)
        return [
            InvestorInfo(
                id=UUID(r.id),
                name=r.name,
                entity_type=InvestorEntityType(r.entity_type),
                tax_jurisdiction=r.tax_jurisdiction,
                contact_email=r.contact_email,
                is_active=r.is_active,
            )
            for r in records
        ]

    async def get_capital_accounts(
        self, *, session: AsyncSession | None = None
    ) -> list[CapitalAccountSummary]:
        """Get latest capital account snapshot for all investors in the fund."""
        accounts = await self._account_repo.get_latest_by_fund(session=session)
        investors = await self._investor_repo.get_all_active(session=session)
        investor_map = {r.id: r.name for r in investors}

        return [
            CapitalAccountSummary(
                id=UUID(a.id),
                investor_id=UUID(a.investor_id),
                investor_name=investor_map.get(a.investor_id, "Unknown"),
                share_class=a.share_class,
                beginning_capital=a.beginning_capital,
                contributions=a.contributions,
                withdrawals=a.withdrawals,
                pnl_allocation=a.pnl_allocation,
                management_fee_allocation=a.management_fee_allocation,
                performance_fee_allocation=a.performance_fee_allocation,
                ending_capital=a.ending_capital,
                ownership_pct=a.ownership_pct,
                shares_held=a.shares_held,
                effective_date=a.effective_date,
            )
            for a in accounts
        ]

    async def get_investor_history(
        self,
        investor_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[CapitalAccountSummary]:
        accounts = await self._account_repo.get_by_investor(investor_id, session=session)
        investor = await self._investor_repo.get_by_id(investor_id, session=session)
        name = investor.name if investor else "Unknown"

        return [
            CapitalAccountSummary(
                id=UUID(a.id),
                investor_id=UUID(a.investor_id),
                investor_name=name,
                share_class=a.share_class,
                beginning_capital=a.beginning_capital,
                contributions=a.contributions,
                withdrawals=a.withdrawals,
                pnl_allocation=a.pnl_allocation,
                management_fee_allocation=a.management_fee_allocation,
                performance_fee_allocation=a.performance_fee_allocation,
                ending_capital=a.ending_capital,
                ownership_pct=a.ownership_pct,
                shares_held=a.shares_held,
                effective_date=a.effective_date,
            )
            for a in accounts
        ]

    async def get_transactions(
        self,
        investor_id: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[CapitalTransaction]:
        records = await self._transaction_repo.get_by_investor(investor_id, session=session)
        return [
            CapitalTransaction(
                id=UUID(r.id),
                capital_account_id=UUID(r.capital_account_id),
                transaction_type=TransactionType(r.transaction_type),
                amount=r.amount,
                shares=r.shares,
                nav_per_share=r.nav_per_share,
                business_date=r.business_date,
                notes=r.notes,
                created_at=r.created_at,
            )
            for r in records
        ]

    async def get_fund_overview(
        self, *, session: AsyncSession | None = None
    ) -> FundCapitalOverview:
        accounts = await self._account_repo.get_latest_by_fund(session=session)
        if not accounts:
            return FundCapitalOverview(
                total_aum=ZERO,
                total_investors=0,
                total_shares_outstanding=ZERO,
                largest_investor_pct=ZERO,
            )

        total_aum = Decimal(sum(a.ending_capital for a in accounts))
        total_shares = Decimal(sum(a.shares_held for a in accounts))
        max_pct = max(a.ownership_pct for a in accounts) if accounts else ZERO
        last_date = max(a.effective_date for a in accounts) if accounts else None

        return FundCapitalOverview(
            total_aum=total_aum,
            total_investors=len(accounts),
            total_shares_outstanding=total_shares,
            largest_investor_pct=max_pct,
            last_allocation_date=last_date,
        )

    async def get_share_class_nav(
        self,
        share_class: str,
        *,
        session: AsyncSession | None = None,
    ) -> tuple[Decimal, Decimal, Decimal]:
        """Get (total_aum, total_shares, nav_per_share) for a share class."""
        accounts = await self._account_repo.get_latest_by_share_class(
            share_class,
            session=session,
        )
        total_aum = sum((a.ending_capital for a in accounts), ZERO)
        total_shares = sum((a.shares_held for a in accounts), ZERO)
        nav = total_aum / total_shares if total_shares > ZERO else ZERO
        return total_aum, total_shares, nav

    async def list_share_classes(self, *, session: AsyncSession | None = None) -> list[str]:
        """Get distinct share classes with active capital accounts."""
        accounts = await self._account_repo.get_latest_by_fund(session=session)
        return sorted({a.share_class for a in accounts})

    async def get_total_shares(self, *, session: AsyncSession | None = None) -> Decimal:
        """Total shares outstanding across all investors."""
        return await self._account_repo.get_total_shares(session=session)

    # ------------------------------------------------------------------
    # EOD: P&L + Fee Allocation
    # ------------------------------------------------------------------

    async def allocate_daily(
        self,
        *,
        fund_pnl: Decimal,
        management_fee: Decimal,
        performance_fee: Decimal,
        nav_per_share: Decimal,
        business_date: date,
        class_fees: dict[str, tuple[Decimal, Decimal]] | None = None,
        session: AsyncSession | None = None,
    ) -> int:
        """Run daily capital allocation: distribute P&L and fees, create new snapshots.

        Called by the EOD orchestrator after NAV calculation and fee accrual.

        Args:
            class_fees: Optional per-class fee overrides mapping
                share_class → (management_fee, performance_fee). When provided,
                fees are allocated per share class instead of using the
                fund-level management_fee/performance_fee.

        Returns the number of accounts allocated.
        """
        current = await self._account_repo.get_latest_by_fund(session=session)
        if not current:
            return 0

        # Build allocation inputs
        inputs = [(a.id, a.ending_capital, a.ownership_pct) for a in current]

        # 1. Allocate P&L proportional to ownership (shared across all classes)
        pnl_results = allocate_pnl(inputs, fund_pnl)
        pnl_map = {aid: pnl for aid, pnl, _ in pnl_results}
        post_pnl_cap = {aid: cap for aid, _, cap in pnl_results}

        # 2. Allocate fees — per-class if class_fees provided, else fund-level
        mgmt_map: dict[str, Decimal] = {}
        perf_map: dict[str, Decimal] = {}
        final_cap: dict[str, Decimal] = {}

        if class_fees:
            # Group accounts by share class
            classes: dict[str, list[tuple[str, Decimal, Decimal]]] = {}
            for a in current:
                cls = a.share_class
                classes.setdefault(cls, []).append((a.id, post_pnl_cap[a.id], a.ownership_pct))

            for cls, cls_accounts in classes.items():
                cls_mgmt, cls_perf = class_fees.get(cls, (ZERO, ZERO))
                # Recompute intra-class ownership for fee allocation
                cls_total = sum(cap for _, cap, _ in cls_accounts)
                if cls_total > ZERO:
                    cls_inputs = [(aid, cap, cap / cls_total) for aid, cap, _ in cls_accounts]
                else:
                    cls_inputs = cls_accounts
                cls_mgmt_results = allocate_fees(cls_inputs, cls_mgmt)
                post_mgmt = [
                    (aid, new_cap, pct)
                    for (aid, _, pct), (_, _, new_cap) in zip(
                        cls_inputs, cls_mgmt_results, strict=True
                    )
                ]
                cls_perf_results = allocate_fees(post_mgmt, cls_perf)
                for (aid, m, _), (_, p, fc) in zip(cls_mgmt_results, cls_perf_results, strict=True):
                    mgmt_map[aid] = m
                    perf_map[aid] = p
                    final_cap[aid] = fc
        else:
            # Legacy fund-level allocation
            post_pnl = [(aid, post_pnl_cap[aid], pct) for aid, _, pct in inputs]
            mgmt_results = allocate_fees(post_pnl, management_fee)
            post_mgmt = [
                (aid, new_cap, pct)
                for (aid, _, pct), (_, _, new_cap) in zip(post_pnl, mgmt_results, strict=True)
            ]
            perf_results = allocate_fees(post_mgmt, performance_fee)
            for (aid, m, _), (_, p, fc) in zip(mgmt_results, perf_results, strict=True):
                mgmt_map[aid] = m
                perf_map[aid] = p
                final_cap[aid] = fc

        # 3. Recompute ownership from final capitals
        final_capitals = [(a.id, final_cap[a.id]) for a in current]
        ownership = recompute_ownership(final_capitals)
        ownership_map = dict(ownership)

        # 4. Create new snapshots + transactions
        count = 0

        for a in current:
            aid = a.id
            pnl_alloc = pnl_map[aid]
            mgmt_alloc = mgmt_map[aid]
            perf_alloc = perf_map[aid]
            new_pct = ownership_map.get(aid, ZERO)

            new_account = CapitalAccountRecord(
                id=str(uuid4()),
                investor_id=a.investor_id,
                share_class=a.share_class,
                beginning_capital=a.ending_capital,
                contributions=ZERO,
                withdrawals=ZERO,
                pnl_allocation=pnl_alloc,
                management_fee_allocation=mgmt_alloc,
                performance_fee_allocation=perf_alloc,
                ending_capital=final_cap[aid],
                ownership_pct=new_pct,
                shares_held=a.shares_held,
                effective_date=business_date,
            )
            await self._account_repo.insert(new_account, session=session)

            # Record P&L transaction
            if pnl_alloc != ZERO:
                await self._transaction_repo.insert(
                    CapitalTransactionRecord(
                        id=str(uuid4()),
                        capital_account_id=new_account.id,
                        investor_id=a.investor_id,
                        transaction_type=TransactionType.PNL_ALLOCATION,
                        amount=pnl_alloc,
                        shares=ZERO,
                        nav_per_share=nav_per_share,
                        business_date=business_date,
                    ),
                    session=session,
                )

            # Record fee transactions
            if mgmt_alloc != ZERO:
                await self._transaction_repo.insert(
                    CapitalTransactionRecord(
                        id=str(uuid4()),
                        capital_account_id=new_account.id,
                        investor_id=a.investor_id,
                        transaction_type=TransactionType.MGMT_FEE_ALLOCATION,
                        amount=mgmt_alloc,
                        shares=ZERO,
                        nav_per_share=nav_per_share,
                        business_date=business_date,
                    ),
                    session=session,
                )

            if perf_alloc != ZERO:
                await self._transaction_repo.insert(
                    CapitalTransactionRecord(
                        id=str(uuid4()),
                        capital_account_id=new_account.id,
                        investor_id=a.investor_id,
                        transaction_type=TransactionType.PERF_FEE_ALLOCATION,
                        amount=perf_alloc,
                        shares=ZERO,
                        nav_per_share=nav_per_share,
                        business_date=business_date,
                    ),
                    session=session,
                )

            count += 1

        logger.info(
            "capital_allocation_complete",
            business_date=str(business_date),
            accounts=count,
            fund_pnl=str(fund_pnl),
        )
        return count

    # ------------------------------------------------------------------
    # Subscriptions (initial + future)
    # ------------------------------------------------------------------

    async def process_subscription(
        self,
        *,
        investor_id: str,
        amount: Decimal,
        nav_per_share: Decimal,
        business_date: date,
        portfolio_id: UUID | None = None,
        currency: str = "USD",
        share_class: str = "default",
        notes: str | None = None,
        session: AsyncSession | None = None,
    ) -> CapitalAccountRecord:
        """Process a capital subscription — issue shares, create account snapshot.

        If *portfolio_id* and a ``CashManagementService`` are configured, a
        corresponding cash credit is recorded automatically.
        """
        shares = compute_subscription_shares(amount, nav_per_share)

        existing = await self._account_repo.get_latest_for_investor(
            investor_id,
            share_class=share_class,
            session=session,
        )

        if existing:
            new_account = CapitalAccountRecord(
                id=str(uuid4()),
                investor_id=investor_id,
                share_class=share_class,
                beginning_capital=existing.ending_capital,
                contributions=amount,
                withdrawals=ZERO,
                pnl_allocation=ZERO,
                management_fee_allocation=ZERO,
                performance_fee_allocation=ZERO,
                ending_capital=existing.ending_capital + amount,
                ownership_pct=ZERO,  # Recomputed after all accounts updated
                shares_held=existing.shares_held + shares,
                effective_date=business_date,
            )
        else:
            new_account = CapitalAccountRecord(
                id=str(uuid4()),
                investor_id=investor_id,
                share_class=share_class,
                beginning_capital=ZERO,
                contributions=amount,
                withdrawals=ZERO,
                pnl_allocation=ZERO,
                management_fee_allocation=ZERO,
                performance_fee_allocation=ZERO,
                ending_capital=amount,
                ownership_pct=ZERO,
                shares_held=shares,
                effective_date=business_date,
            )

        saved = await self._account_repo.insert(new_account, session=session)

        txn_id = str(uuid4())
        await self._transaction_repo.insert(
            CapitalTransactionRecord(
                id=txn_id,
                capital_account_id=saved.id,
                investor_id=investor_id,
                transaction_type=TransactionType.SUBSCRIPTION,
                amount=amount,
                shares=shares,
                nav_per_share=nav_per_share,
                business_date=business_date,
                notes=notes,
            ),
            session=session,
        )

        # Credit cash balance for the subscription inflow
        if self._cash_service is not None and portfolio_id is not None:
            from app.modules.cash_management.interface import CashFlowType

            await self._cash_service.credit(
                portfolio_id=portfolio_id,
                currency=currency,
                amount=amount,
                flow_type=CashFlowType.SUBSCRIPTION,
                reference_id=txn_id,
                description=f"Subscription from investor {investor_id}",
                session=session,
            )

        # Recompute ownership for all accounts
        await self._recompute_all_ownership(business_date, session=session)

        logger.info(
            "subscription_processed",
            investor_id=investor_id,
            amount=str(amount),
            shares=str(shares),
            nav_per_share=str(nav_per_share),
        )
        return saved

    async def process_redemption(
        self,
        *,
        investor_id: str,
        amount: Decimal,
        nav_per_share: Decimal,
        business_date: date,
        portfolio_id: UUID | None = None,
        currency: str = "USD",
        share_class: str = "default",
        notes: str | None = None,
        session: AsyncSession | None = None,
    ) -> CapitalAccountRecord:
        """Process a capital redemption — redeem shares, create account snapshot.

        If *portfolio_id* and a ``CashManagementService`` are configured, a
        corresponding cash debit is recorded automatically.
        """
        existing = await self._account_repo.get_latest_for_investor(
            investor_id,
            share_class=share_class,
            session=session,
        )
        if existing is None:
            msg = f"No capital account found for investor {investor_id}"
            raise ValueError(msg)

        if amount > existing.ending_capital:
            msg = f"Redemption {amount} exceeds ending capital {existing.ending_capital}"
            raise ValueError(msg)

        shares_to_redeem = amount / nav_per_share if nav_per_share > 0 else ZERO
        new_shares = existing.shares_held - shares_to_redeem
        if new_shares < 0:
            new_shares = ZERO

        new_account = CapitalAccountRecord(
            id=str(uuid4()),
            investor_id=investor_id,
            share_class=existing.share_class,
            beginning_capital=existing.ending_capital,
            contributions=ZERO,
            withdrawals=amount,
            pnl_allocation=ZERO,
            management_fee_allocation=ZERO,
            performance_fee_allocation=ZERO,
            ending_capital=existing.ending_capital - amount,
            ownership_pct=ZERO,
            shares_held=new_shares,
            effective_date=business_date,
        )

        saved = await self._account_repo.insert(new_account, session=session)

        txn_id = str(uuid4())
        await self._transaction_repo.insert(
            CapitalTransactionRecord(
                id=txn_id,
                capital_account_id=saved.id,
                investor_id=investor_id,
                transaction_type=TransactionType.REDEMPTION,
                amount=-amount,
                shares=-shares_to_redeem,
                nav_per_share=nav_per_share,
                business_date=business_date,
                notes=notes,
            ),
            session=session,
        )

        # Debit cash balance for the redemption outflow
        if self._cash_service is not None and portfolio_id is not None:
            from app.modules.cash_management.interface import CashFlowType

            await self._cash_service.debit(
                portfolio_id=portfolio_id,
                currency=currency,
                amount=amount,
                flow_type=CashFlowType.REDEMPTION,
                reference_id=txn_id,
                description=f"Redemption for investor {investor_id}",
                session=session,
            )

        await self._recompute_all_ownership(business_date, session=session)

        logger.info(
            "redemption_processed",
            investor_id=investor_id,
            amount=str(amount),
            shares_redeemed=str(shares_to_redeem),
            nav_per_share=str(nav_per_share),
        )
        return saved

    async def _recompute_all_ownership(
        self,
        business_date: date,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        """Recompute ownership percentages for all accounts at a given date."""
        accounts = await self._account_repo.get_latest_by_fund(session=session)
        if not accounts:
            return

        inputs = [(a.id, a.ending_capital) for a in accounts]
        new_ownership = recompute_ownership(inputs)

        # Update in-place (these are the latest snapshots for today)
        ownership_map = dict(new_ownership)
        for a in accounts:
            if a.effective_date == business_date:
                a.ownership_pct = ownership_map.get(a.id, ZERO)
