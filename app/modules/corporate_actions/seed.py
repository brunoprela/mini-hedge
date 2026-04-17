"""Seed data for corporate actions — sample processed dividends and splits."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import structlog

from app.modules.corporate_actions.interfaces import ActionType, ProcessingStatus
from app.modules.corporate_actions.models import ProcessedCorporateActionRecord

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.shared.database import TenantSessionFactory

logger = structlog.get_logger()

# Sample processed corporate actions for dev environment
_SEED_ACTIONS = [
    {
        "action_id": "DIV-AAPL-2026Q1",
        "instrument_id": "AAPL",
        "action_type": ActionType.DIVIDEND.value,
        "ex_date": date(2026, 2, 7),
        "status": ProcessingStatus.PROCESSED.value,
        "adjustments": [
            {
                "instrument_id": "AAPL",
                "quantity_delta": "0",
                "cost_basis_adjustment": "0",
                "cash_amount": "2500.00",
            }
        ],
    },
    {
        "action_id": "DIV-MSFT-2026Q1",
        "instrument_id": "MSFT",
        "action_type": ActionType.DIVIDEND.value,
        "ex_date": date(2026, 2, 20),
        "status": ProcessingStatus.PROCESSED.value,
        "adjustments": [
            {
                "instrument_id": "MSFT",
                "quantity_delta": "0",
                "cost_basis_adjustment": "0",
                "cash_amount": "1875.00",
            }
        ],
    },
    {
        "action_id": "DIV-JPM-2026Q1",
        "instrument_id": "JPM",
        "action_type": ActionType.DIVIDEND.value,
        "ex_date": date(2026, 1, 3),
        "status": ProcessingStatus.PROCESSED.value,
        "adjustments": [
            {
                "instrument_id": "JPM",
                "quantity_delta": "0",
                "cost_basis_adjustment": "0",
                "cash_amount": "3200.00",
            }
        ],
    },
    {
        "action_id": "SPLIT-NVDA-2026",
        "instrument_id": "NVDA",
        "action_type": ActionType.STOCK_SPLIT.value,
        "ex_date": date(2026, 3, 10),
        "status": ProcessingStatus.PROCESSED.value,
        "adjustments": [
            {
                "instrument_id": "NVDA",
                "quantity_delta": "500",
                "cost_basis_adjustment": "-50.00",
                "cash_amount": "0",
            }
        ],
    },
]


async def seed_dev_data(app: FastAPI, sf: TenantSessionFactory) -> None:
    """Idempotent dev-only seeding for processed corporate actions."""
    service = getattr(app.state, "corporate_actions_service", None)
    if service is None:
        logger.debug("corporate_actions_seed_skipped", reason="service not available")
        return

    fund_repo = getattr(app.state, "fund_repo", None)
    if fund_repo is None:
        logger.debug("corporate_actions_seed_skipped", reason="fund_repo not available")
        return

    ca_repo = service._repo
    active_funds = await fund_repo.list_active()
    seeded = 0

    for fund in active_funds:
        async with sf.fund_scope(fund.slug):
            for action_data in _SEED_ACTIONS:
                existing = await ca_repo.get_by_action_id(action_data["action_id"])
                if existing is not None:
                    continue

                record = ProcessedCorporateActionRecord(
                    id=str(uuid4()),
                    action_id=action_data["action_id"],
                    instrument_id=action_data["instrument_id"],
                    action_type=action_data["action_type"],
                    ex_date=action_data["ex_date"],
                    status=action_data["status"],
                    adjustments=action_data["adjustments"],
                    processed_at=datetime.now(UTC),
                )
                await ca_repo.insert(record)
                seeded += 1

    if seeded:
        logger.info("corporate_actions_seed_complete", count=seeded)
    else:
        logger.debug("corporate_actions_seed_skipped", reason="data already exists")
