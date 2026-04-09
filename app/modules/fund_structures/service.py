"""Fund structures service — master-feeder, strategy books, fund of funds."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from app.modules.fund_structures.interface import (
    BookRebalanceResult,
    FeederSubscription,
    FundOfFundsHolding,
    FundOfFundsNAV,
    MasterFeederLink,
    StrategyBook,
)
from app.modules.fund_structures.models import (
    FundOfFundsHoldingRecord,
    MasterFeederLinkRecord,
    StrategyBookRecord,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.fund_structures.repository import (
        FundOfFundsRepository,
        MasterFeederRepository,
        StrategyBookRepository,
    )
    from app.shared.database import TenantSessionFactory
    from app.shared.events import EventBus

logger = structlog.get_logger()

ZERO = Decimal(0)


class FundStructuresService:
    """Manages master-feeder links, strategy book hierarchies, and FoF holdings."""

    def __init__(
        self,
        *,
        master_feeder_repo: MasterFeederRepository,
        strategy_book_repo: StrategyBookRepository,
        fof_repo: FundOfFundsRepository,
        session_factory: TenantSessionFactory,
        event_bus: EventBus | None = None,
    ) -> None:
        self._mf_repo = master_feeder_repo
        self._sb_repo = strategy_book_repo
        self._fof_repo = fof_repo
        self._session_factory = session_factory
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # 6A  Master-Feeder
    # ------------------------------------------------------------------

    async def create_master_feeder_link(
        self,
        master_slug: str,
        feeder_slug: str,
        allocation_pct: Decimal,
        *,
        session: AsyncSession | None = None,
    ) -> MasterFeederLink:
        record = MasterFeederLinkRecord(
            master_fund_slug=master_slug,
            feeder_fund_slug=feeder_slug,
            allocation_pct=allocation_pct,
        )
        await self._mf_repo.create_link(record, session=session)
        logger.info(
            "master_feeder_link_created",
            master=master_slug,
            feeder=feeder_slug,
            allocation_pct=str(allocation_pct),
        )
        if self._event_bus:
            from app.shared.audit.events import AuditEventType
            from app.shared.events import BaseEvent
            from app.shared.schema_registry import shared_topic

            await self._event_bus.publish(
                shared_topic("audit"),
                BaseEvent(
                    event_type=AuditEventType.MASTER_FEEDER_LINK_CREATED,
                    fund_slug=master_slug,
                    data={
                        "link_id": record.id,
                        "master_fund_slug": master_slug,
                        "feeder_fund_slug": feeder_slug,
                        "allocation_pct": str(allocation_pct),
                    },
                ),
            )
        return self._to_mf_link(record)

    async def get_feeder_structure(
        self,
        master_slug: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[MasterFeederLink]:
        records = await self._mf_repo.get_feeders_for_master(
            master_slug,
            session=session,
        )
        return [self._to_mf_link(r) for r in records]

    async def allocate_feeder_subscription(
        self,
        feeder_slug: str,
        amount: Decimal,
        *,
        session: AsyncSession | None = None,
    ) -> FeederSubscription:
        """Calculate how much of a feeder subscription flows to the master."""
        link = await self._mf_repo.get_master_for_feeder(
            feeder_slug,
            session=session,
        )
        if link is None:
            return FeederSubscription(
                feeder_fund_slug=feeder_slug,
                amount=amount,
                allocated_to_master=ZERO,
            )
        allocated = amount * link.allocation_pct
        return FeederSubscription(
            feeder_fund_slug=feeder_slug,
            amount=amount,
            allocated_to_master=allocated,
        )

    async def compute_feeder_nav(
        self,
        feeder_slug: str,
        master_nav: Decimal,
        *,
        session: AsyncSession | None = None,
    ) -> Decimal:
        """Compute feeder NAV as its allocation_pct * master NAV."""
        link = await self._mf_repo.get_master_for_feeder(
            feeder_slug,
            session=session,
        )
        if link is None:
            return ZERO
        return link.allocation_pct * master_nav

    # ------------------------------------------------------------------
    # 6B  Strategy Books
    # ------------------------------------------------------------------

    async def create_book(
        self,
        fund_slug: str,
        name: str,
        level: str,
        parent_id: str | None = None,
        portfolio_id: str | None = None,
        target_pct: Decimal = Decimal("1.0"),
        *,
        session: AsyncSession | None = None,
    ) -> StrategyBook:
        record = StrategyBookRecord(
            fund_slug=fund_slug,
            name=name,
            level=level,
            parent_id=parent_id,
            portfolio_id=portfolio_id,
            target_allocation_pct=target_pct,
        )
        await self._sb_repo.create(record, session=session)
        logger.info("strategy_book_created", fund=fund_slug, name=name, level=level)
        if self._event_bus:
            from app.shared.audit.events import AuditEventType
            from app.shared.events import BaseEvent
            from app.shared.schema_registry import shared_topic

            await self._event_bus.publish(
                shared_topic("audit"),
                BaseEvent(
                    event_type=AuditEventType.STRATEGY_BOOK_CREATED,
                    fund_slug=fund_slug,
                    data={
                        "book_id": record.id,
                        "fund_slug": fund_slug,
                        "name": name,
                        "level": level,
                        "parent_id": parent_id,
                        "target_pct": str(target_pct),
                    },
                ),
            )
        return self._to_strategy_book(record)

    async def get_book_tree(
        self,
        fund_slug: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[StrategyBook]:
        records = await self._sb_repo.get_tree(fund_slug, session=session)
        return [self._to_strategy_book(r) for r in records]

    async def check_rebalance(
        self,
        fund_slug: str,
        book_navs: dict[UUID, Decimal],
        *,
        session: AsyncSession | None = None,
    ) -> list[BookRebalanceResult]:
        """Compare actual allocations vs targets and compute drift."""
        records = await self._sb_repo.get_tree(fund_slug, session=session)
        total_nav = sum(book_navs.values()) if book_navs else ZERO
        if total_nav == ZERO:
            return []

        results: list[BookRebalanceResult] = []
        for r in records:
            book_id = UUID(r.id)
            current_nav = book_navs.get(book_id, ZERO)
            current_pct = current_nav / total_nav
            target_pct = r.target_allocation_pct
            drift = current_pct - target_pct
            suggested = drift * total_nav  # negative = need to buy
            results.append(
                BookRebalanceResult(
                    book_id=book_id,
                    book_name=r.name,
                    target_pct=target_pct,
                    current_pct=current_pct,
                    drift_pct=drift,
                    suggested_trade_amount=suggested,
                ),
            )
        return results

    # ------------------------------------------------------------------
    # 6C  Fund of Funds
    # ------------------------------------------------------------------

    async def add_fof_holding(
        self,
        fof_slug: str,
        underlying_name: str,
        allocation_pct: Decimal,
        underlying_slug: str | None = None,
        is_internal: bool = False,
        *,
        session: AsyncSession | None = None,
    ) -> FundOfFundsHolding:
        record = FundOfFundsHoldingRecord(
            fof_fund_slug=fof_slug,
            underlying_fund_slug=underlying_slug,
            underlying_fund_name=underlying_name,
            allocation_pct=allocation_pct,
            is_internal=is_internal,
        )
        await self._fof_repo.add_holding(record, session=session)
        logger.info(
            "fof_holding_added",
            fof=fof_slug,
            underlying=underlying_name,
            allocation_pct=str(allocation_pct),
        )
        if self._event_bus:
            from app.shared.audit.events import AuditEventType
            from app.shared.events import BaseEvent
            from app.shared.schema_registry import shared_topic

            await self._event_bus.publish(
                shared_topic("audit"),
                BaseEvent(
                    event_type=AuditEventType.FOF_HOLDING_ADDED,
                    fund_slug=fof_slug,
                    data={
                        "holding_id": record.id,
                        "fof_fund_slug": fof_slug,
                        "underlying_fund_name": underlying_name,
                        "underlying_fund_slug": underlying_slug,
                        "allocation_pct": str(allocation_pct),
                        "is_internal": is_internal,
                    },
                ),
            )
        return self._to_fof_holding(record)

    async def get_fof_holdings(
        self,
        fof_slug: str,
        *,
        session: AsyncSession | None = None,
    ) -> list[FundOfFundsHolding]:
        records = await self._fof_repo.list_holdings(fof_slug, session=session)
        return [self._to_fof_holding(r) for r in records]

    async def compute_fof_nav(
        self,
        fof_slug: str,
        *,
        session: AsyncSession | None = None,
    ) -> FundOfFundsNAV:
        """Sum NAVs of underlying holdings."""
        records = await self._fof_repo.list_holdings(fof_slug, session=session)
        holdings = [self._to_fof_holding(r) for r in records]
        total = sum((h.current_nav for h in holdings), ZERO)
        return FundOfFundsNAV(
            fof_fund_slug=fof_slug,
            total_nav=total,
            holdings=holdings,
            computed_at=datetime.now(UTC),
        )

    async def update_holding_nav(
        self,
        holding_id: str,
        nav: Decimal,
        *,
        session: AsyncSession | None = None,
    ) -> None:
        await self._fof_repo.update_nav(holding_id, nav, session=session)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_mf_link(r: MasterFeederLinkRecord) -> MasterFeederLink:
        return MasterFeederLink(
            id=UUID(r.id),
            master_fund_slug=r.master_fund_slug,
            feeder_fund_slug=r.feeder_fund_slug,
            allocation_pct=r.allocation_pct,
            is_active=r.is_active,
            created_at=r.created_at,
        )

    @staticmethod
    def _to_strategy_book(r: StrategyBookRecord) -> StrategyBook:
        return StrategyBook(
            id=UUID(r.id),
            fund_slug=r.fund_slug,
            name=r.name,
            level=r.level,
            parent_id=UUID(r.parent_id) if r.parent_id else None,
            portfolio_id=UUID(r.portfolio_id) if r.portfolio_id else None,
            target_allocation_pct=r.target_allocation_pct,
            actual_allocation_pct=None,
            is_active=r.is_active,
        )

    @staticmethod
    def _to_fof_holding(r: FundOfFundsHoldingRecord) -> FundOfFundsHolding:
        return FundOfFundsHolding(
            id=UUID(r.id),
            fof_fund_slug=r.fof_fund_slug,
            underlying_fund_slug=r.underlying_fund_slug,
            underlying_fund_name=r.underlying_fund_name,
            allocation_pct=r.allocation_pct,
            current_nav=r.current_nav,
            is_internal=r.is_internal,
        )
