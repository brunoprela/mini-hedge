"""Capital accounts service — read-only queries on investor capital accounts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from app.modules.capital_accounts.interfaces import (
    CapitalAccountSummary,
    CapitalTransaction,
    FundCapitalOverview,
    InvestorEntityType,
    InvestorInfo,
    TransactionType,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.capital_accounts.repositories.account import CapitalAccountRepository
    from app.modules.capital_accounts.repositories.investor import InvestorRepository
    from app.modules.capital_accounts.repositories.transaction import (
        CapitalTransactionRepository,
    )

logger = structlog.get_logger()

ZERO = Decimal(0)


class CapitalAccountService:
    """Read-only queries on investor capital accounts."""

    def __init__(
        self,
        *,
        investor_repo: InvestorRepository,
        account_repo: CapitalAccountRepository,
        transaction_repo: CapitalTransactionRepository,
    ) -> None:
        self._investor_repo = investor_repo
        self._account_repo = account_repo
        self._transaction_repo = transaction_repo

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
        from_date: date | None = None,
        to_date: date | None = None,
        session: AsyncSession | None = None,
    ) -> list[CapitalAccountSummary]:
        accounts = await self._account_repo.get_by_investor(
            investor_id, from_date=from_date, to_date=to_date, session=session
        )
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
        from_date: date | None = None,
        to_date: date | None = None,
        session: AsyncSession | None = None,
    ) -> list[CapitalTransaction]:
        records = await self._transaction_repo.get_by_investor(
            investor_id, from_date=from_date, to_date=to_date, session=session
        )
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

    async def get_share_class_investor_count(
        self,
        share_class: str,
        *,
        session: AsyncSession | None = None,
    ) -> int:
        """Count of investors holding a given share class."""
        accounts = await self._account_repo.get_latest_by_share_class(
            share_class, session=session
        )
        return len(accounts)

    async def get_total_shares(self, *, session: AsyncSession | None = None) -> Decimal:
        """Total shares outstanding across all investors."""
        return await self._account_repo.get_total_shares(session=session)
