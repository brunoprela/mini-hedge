"""Counterparty risk service — counterparty exposures and credit risk."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from app.modules.risk_engine.interfaces.counterparty import (
    CounterpartyExposure,
    CounterpartyInfo,
    CounterpartyType,
)
from app.modules.risk_engine.models.counterparty_exposure import CounterpartyExposureRecord

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.risk_engine.repositories import (
        CounterpartyExposureRepository,
        CounterpartyRepository,
    )

logger = structlog.get_logger()

ZERO = Decimal(0)


class CounterpartyRiskService:
    """Manages counterparty exposures and credit risk."""

    def __init__(
        self,
        *,
        counterparty_repo: CounterpartyRepository,
        counterparty_exposure_repo: CounterpartyExposureRepository,
    ) -> None:
        self._counterparty_repo = counterparty_repo
        self._counterparty_exposure_repo = counterparty_exposure_repo

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_counterparty_exposures(
        self,
        portfolio_id: UUID,
        *,
        session: AsyncSession | None = None,
    ) -> list[CounterpartyExposure]:
        """Get latest counterparty exposure for a portfolio."""
        records = await self._counterparty_exposure_repo.get_counterparty_exposures(
            portfolio_id,
            session=session,
        )
        cpty_map = await self._counterparty_repo.get_counterparty_map(session=session)
        return [
            CounterpartyExposure(
                counterparty_id=UUID(r.counterparty_id),
                counterparty_name=cpty_map.get(r.counterparty_id, "Unknown"),
                portfolio_id=UUID(r.portfolio_id),
                business_date=r.business_date,
                gross_exposure=r.gross_exposure,
                net_exposure=r.net_exposure,
                collateral_held=r.collateral_held,
                collateral_posted=r.collateral_posted,
                credit_limit=r.credit_limit,
                utilization_pct=r.utilization_pct,
                breach=r.breach,
            )
            for r in records
        ]

    async def list_counterparties(
        self, *, session: AsyncSession | None = None
    ) -> list[CounterpartyInfo]:
        records = await self._counterparty_repo.list_counterparties(session=session)
        return [
            CounterpartyInfo(
                id=UUID(r.id),
                name=r.name,
                counterparty_type=CounterpartyType(r.counterparty_type),
                credit_rating=r.credit_rating,
                credit_limit=r.credit_limit,
                netting_eligible=r.netting_eligible,
                is_active=r.is_active,
            )
            for r in records
        ]

    async def record_counterparty_exposure(
        self,
        *,
        counterparty_id: str,
        portfolio_id: UUID,
        business_date: datetime,
        gross_exposure: Decimal,
        net_exposure: Decimal,
        collateral_held: Decimal = ZERO,
        collateral_posted: Decimal = ZERO,
        session: AsyncSession | None = None,
    ) -> None:
        """Record or update counterparty exposure snapshot."""
        cpty = await self._counterparty_repo.get_counterparty(counterparty_id, session=session)
        credit_limit = cpty.credit_limit if cpty else ZERO
        util = net_exposure / credit_limit if credit_limit > 0 else Decimal(999)
        breach = net_exposure > credit_limit if credit_limit > 0 else False

        record = CounterpartyExposureRecord(
            id=str(uuid4()),
            counterparty_id=counterparty_id,
            portfolio_id=str(portfolio_id),
            business_date=business_date,
            gross_exposure=gross_exposure,
            net_exposure=net_exposure,
            collateral_held=collateral_held,
            collateral_posted=collateral_posted,
            credit_limit=credit_limit,
            utilization_pct=util,
            breach=breach,
        )
        await self._counterparty_exposure_repo.insert_counterparty_exposure(record, session=session)

        if breach:
            logger.warning(
                "counterparty_limit_breach",
                counterparty_id=counterparty_id,
                net_exposure=str(net_exposure),
                credit_limit=str(credit_limit),
            )
