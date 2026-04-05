"""Corporate actions engine — generates realistic corporate action events.

Deterministic generation based on date + instrument ticker so results are
reproducible across restarts.
"""

from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta
from typing import TYPE_CHECKING

import structlog

from mock_exchange.corporate_actions.models import CorporateAction, CorporateActionType
from mock_exchange.reference_data.instruments import INSTRUMENT_UNIVERSE

if TYPE_CHECKING:
    from mock_exchange.shared.kafka import MockExchangeProducer

logger = structlog.get_logger()

CORPORATE_ACTIONS_TOPIC = "shared.corporate-actions"


def _seed_for(ticker: str, business_date: date) -> int:
    """Deterministic seed from ticker + date."""
    raw = f"{ticker}:{business_date.isoformat()}"
    return int(hashlib.sha256(raw.encode()).hexdigest()[:8], 16)


class CorporateActionsEngine:
    """Generates periodic corporate actions for the instrument universe."""

    def __init__(self, producer: MockExchangeProducer | None = None) -> None:
        self._producer = producer
        self._actions: dict[str, CorporateAction] = {}

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def generate_actions(self, business_date: date) -> list[CorporateAction]:
        """Generate corporate actions for a given business date.

        Deterministic: the same date always produces the same actions.
        """
        generated: list[CorporateAction] = []

        for instrument in INSTRUMENT_UNIVERSE:
            rng = random.Random(_seed_for(instrument.ticker, business_date))

            ticker = instrument.ticker
            ccy = instrument.currency

            # ~15% chance of a dividend on any given business date — roughly
            # quarterly when called daily.
            if rng.random() < 0.15:
                action = self._make_dividend(ticker, ccy, business_date, rng)
                generated.append(action)

            # 1.5% chance of a stock split
            if rng.random() < 0.015:
                action = self._make_stock_split(ticker, ccy, business_date, rng)
                generated.append(action)

            # 0.3% chance of a merger event
            if rng.random() < 0.003:
                action = self._make_merger(ticker, ccy, business_date, rng)
                generated.append(action)

        # Store and optionally publish
        for action in generated:
            self._actions[action.action_id] = action
            self._publish(action)

        logger.info(
            "corporate_actions_generated",
            date=business_date.isoformat(),
            count=len(generated),
        )
        return generated

    def get_pending_actions(
        self,
        start_date: date,
        end_date: date,
    ) -> list[CorporateAction]:
        """Return actions whose ex_date falls within [start_date, end_date]."""
        return [
            a
            for a in self._actions.values()
            if start_date <= a.ex_date <= end_date
        ]

    def get_all_actions(
        self,
        instrument_id: str | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> list[CorporateAction]:
        """Return actions with optional filtering."""
        result = list(self._actions.values())
        if instrument_id:
            result = [a for a in result if a.instrument_id == instrument_id]
        if start:
            result = [a for a in result if a.ex_date >= start]
        if end:
            result = [a for a in result if a.ex_date <= end]
        return result

    def get_action(self, action_id: str) -> CorporateAction | None:
        return self._actions.get(action_id)

    # ------------------------------------------------------------------
    #  Private helpers
    # ------------------------------------------------------------------

    def _make_action_id(self, ticker: str, action_type: str, business_date: date) -> str:
        raw = f"{ticker}:{action_type}:{business_date.isoformat()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _make_dividend(
        self,
        ticker: str,
        currency: str,
        business_date: date,
        rng: random.Random,
    ) -> CorporateAction:
        amount = round(rng.uniform(0.10, 2.00), 2)
        ex_date = business_date
        record_date = business_date + timedelta(days=1)
        pay_date = business_date + timedelta(days=rng.randint(14, 30))

        return CorporateAction(
            action_id=self._make_action_id(ticker, "dividend", business_date),
            instrument_id=ticker,
            action_type=CorporateActionType.DIVIDEND,
            ex_date=ex_date,
            record_date=record_date,
            pay_date=pay_date,
            amount=str(amount),
            currency=currency,
            status="announced",
        )

    def _make_stock_split(
        self,
        ticker: str,
        currency: str,
        business_date: date,
        rng: random.Random,
    ) -> CorporateAction:
        ratio = rng.choice(["2:1", "3:1"])
        ex_date = business_date + timedelta(days=rng.randint(7, 21))
        record_date = ex_date + timedelta(days=1)
        pay_date = ex_date + timedelta(days=rng.randint(3, 7))

        return CorporateAction(
            action_id=self._make_action_id(ticker, "stock_split", business_date),
            instrument_id=ticker,
            action_type=CorporateActionType.STOCK_SPLIT,
            ex_date=ex_date,
            record_date=record_date,
            pay_date=pay_date,
            currency=currency,
            ratio=ratio,
            status="announced",
        )

    def _make_merger(
        self,
        ticker: str,
        currency: str,
        business_date: date,
        rng: random.Random,
    ) -> CorporateAction:
        amount = round(rng.uniform(10.0, 200.0), 2)
        ex_date = business_date + timedelta(days=rng.randint(30, 90))

        return CorporateAction(
            action_id=self._make_action_id(ticker, "merger", business_date),
            instrument_id=ticker,
            action_type=CorporateActionType.MERGER,
            ex_date=ex_date,
            currency=currency,
            amount=str(amount),
            status="proposed",
        )

    def _publish(self, action: CorporateAction) -> None:
        if self._producer is None:
            return
        self._producer.produce(
            topic=CORPORATE_ACTIONS_TOPIC,
            event_type="corporate_action.announced",
            data=action.model_dump(mode="json"),
        )
        self._producer.flush(timeout=0.5)
