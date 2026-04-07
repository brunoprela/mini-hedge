"""FX forward pricing and OTC execution simulation.

Uses yield curves + spot rates to price FX forwards via covered interest
rate parity. Simulates counterparty execution with configurable spread
markups and latency.

Forward rate: F = S * exp((r_quote - r_base) * T)
  (continuous compounding version — consistent with yield curve rates)
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from mock_exchange.market_data.simulator import GBMSimulator
    from mock_exchange.market_data.yield_curve import YieldCurveSimulator
    from mock_exchange.shared.kafka import MockExchangeProducer

logger = structlog.get_logger()

FX_FORWARDS_TOPIC = "shared.fx-forwards"
INTEREST_RATES_TOPIC = "shared.interest-rates"

_Q6 = Decimal("0.000001")
_Q4 = Decimal("0.0001")
_Q2 = Decimal("0.01")


@dataclass(frozen=True)
class ForwardQuote:
    """A quoted FX forward rate with bid/ask."""

    base_currency: str
    quote_currency: str
    tenor_days: int
    spot_mid: Decimal
    forward_mid: Decimal
    forward_bid: Decimal
    forward_ask: Decimal
    forward_points: Decimal  # forward - spot (in pips)
    domestic_rate: Decimal  # quote currency rate
    foreign_rate: Decimal  # base currency rate
    timestamp: datetime


@dataclass(frozen=True)
class ForwardExecution:
    """Confirmation of an FX forward booking."""

    execution_id: str
    base_currency: str
    quote_currency: str
    direction: str  # "buy" or "sell"
    notional: Decimal
    contract_rate: Decimal
    spot_at_inception: Decimal
    tenor_days: int
    trade_date: date
    maturity_date: date
    counterparty: str
    executed_at: datetime


@dataclass
class FXForwardService:
    """FX forward pricing and OTC execution simulation.

    Acts as the mock "counterparty bank" that quotes forwards and
    books executions. Uses yield curves for interest rate parity pricing.
    """

    yield_curves: YieldCurveSimulator
    simulator: GBMSimulator | None = None
    producer: MockExchangeProducer | None = None

    # Counterparty spread markup in bps (applied to forward rate)
    spread_markup_bps: float = 3.0
    # Simulated execution latency (not actually delayed — just reported)
    latency_ms: int = 50
    # Counterparty name
    counterparty_name: str = "MOCK-BANK-1"

    # Booked forwards (in-memory ledger)
    _booked: dict[str, ForwardExecution] = field(default_factory=dict, init=False)

    def quote_forward(
        self,
        base_currency: str,
        quote_currency: str,
        tenor_days: int,
    ) -> ForwardQuote | None:
        """Quote an FX forward using yield curves and spot rates.

        Uses continuous compounding: F = S * exp((r_q - r_b) * T)
        where r_q = quote (domestic) rate, r_b = base (foreign) rate.
        """
        spot = self._get_spot(base_currency, quote_currency)
        if spot is None:
            logger.warning(
                "fx_forward_no_spot",
                base=base_currency,
                quote=quote_currency,
            )
            return None

        # Get interpolated rates from yield curves
        r_base = self.yield_curves.get_rate(base_currency, tenor_days)
        r_quote = self.yield_curves.get_rate(quote_currency, tenor_days)
        if r_base is None or r_quote is None:
            logger.warning(
                "fx_forward_no_curve",
                base=base_currency,
                quote=quote_currency,
                r_base_available=r_base is not None,
                r_quote_available=r_quote is not None,
            )
            return None

        t = tenor_days / 360.0
        # Forward rate via covered interest rate parity
        fwd_float = float(spot) * math.exp((r_quote - r_base) * t)
        fwd_mid = Decimal(str(fwd_float)).quantize(_Q6, rounding=ROUND_HALF_UP)

        # Apply bid/ask spread
        markup = fwd_mid * Decimal(str(self.spread_markup_bps)) / Decimal("10000")
        half = markup / 2
        fwd_bid = (fwd_mid - half).quantize(_Q6)
        fwd_ask = (fwd_mid + half).quantize(_Q6)

        return ForwardQuote(
            base_currency=base_currency,
            quote_currency=quote_currency,
            tenor_days=tenor_days,
            spot_mid=spot,
            forward_mid=fwd_mid,
            forward_bid=fwd_bid,
            forward_ask=fwd_ask,
            forward_points=(fwd_mid - spot).quantize(_Q6),
            domestic_rate=Decimal(str(round(r_quote, 6))),
            foreign_rate=Decimal(str(round(r_base, 6))),
            timestamp=datetime.now(UTC),
        )

    def execute_forward(
        self,
        base_currency: str,
        quote_currency: str,
        direction: str,
        notional: Decimal,
        tenor_days: int,
    ) -> ForwardExecution | None:
        """Book an FX forward at current market rate.

        Fills at bid (for sells) or ask (for buys) — same as any OTC market.
        """
        quote = self.quote_forward(base_currency, quote_currency, tenor_days)
        if quote is None:
            return None

        contract_rate = quote.forward_ask if direction == "buy" else quote.forward_bid
        today = date.today()
        from datetime import timedelta

        maturity = today + timedelta(days=tenor_days)

        execution = ForwardExecution(
            execution_id=str(uuid.uuid4()),
            base_currency=base_currency,
            quote_currency=quote_currency,
            direction=direction,
            notional=notional,
            contract_rate=contract_rate,
            spot_at_inception=quote.spot_mid,
            tenor_days=tenor_days,
            trade_date=today,
            maturity_date=maturity,
            counterparty=self.counterparty_name,
            executed_at=datetime.now(UTC),
        )

        self._booked[execution.execution_id] = execution

        logger.info(
            "fx_forward_executed",
            execution_id=execution.execution_id,
            pair=f"{base_currency}/{quote_currency}",
            direction=direction,
            notional=str(notional),
            rate=str(contract_rate),
            tenor=tenor_days,
        )

        # Publish execution to Kafka
        if self.producer:
            self.producer.produce(
                topic=FX_FORWARDS_TOPIC,
                event_type="fx.forward.executed",
                data={
                    "execution_id": execution.execution_id,
                    "base_currency": base_currency,
                    "quote_currency": quote_currency,
                    "direction": direction,
                    "notional": str(notional),
                    "contract_rate": str(contract_rate),
                    "spot_at_inception": str(quote.spot_mid),
                    "tenor_days": tenor_days,
                    "trade_date": today.isoformat(),
                    "maturity_date": maturity.isoformat(),
                    "counterparty": self.counterparty_name,
                    "timestamp": execution.executed_at.isoformat(),
                },
            )

        return execution

    def get_execution(self, execution_id: str) -> ForwardExecution | None:
        return self._booked.get(execution_id)

    def list_executions(self) -> list[ForwardExecution]:
        return list(self._booked.values())

    def _get_spot(self, base: str, quote: str) -> Decimal | None:
        """Get FX spot rate from the GBM simulator.

        Simulator stores rates as USD/{quote}, so we need to handle
        both direct and cross-rate lookups.
        """
        if self.simulator is None:
            return None

        # Direct lookup: "FX:USD/GBP"
        pair_id = f"FX:{base}/{quote}"
        rate = self.simulator._fx_rates.get(pair_id)
        if rate is not None:
            return Decimal(str(rate)).quantize(_Q6, rounding=ROUND_HALF_UP)

        # Inverse: "FX:USD/GBP" when we need GBP/USD
        inverse_id = f"FX:{quote}/{base}"
        inv_rate = self.simulator._fx_rates.get(inverse_id)
        if inv_rate is not None and inv_rate > 0:
            return (Decimal(1) / Decimal(str(inv_rate))).quantize(
                _Q6, rounding=ROUND_HALF_UP,
            )

        # Triangulation via USD
        if base != "USD" and quote != "USD":
            base_usd = self.simulator._fx_rates.get(f"FX:USD/{base}")
            quote_usd = self.simulator._fx_rates.get(f"FX:USD/{quote}")
            if base_usd and quote_usd and base_usd > 0:
                cross = quote_usd / base_usd
                return Decimal(str(cross)).quantize(_Q6, rounding=ROUND_HALF_UP)

        return None
