"""Broker profiles — simulated execution characteristics per broker.

Each broker profile defines a distinct execution personality:
latency, commission, fill quality, sector specializations.

Broker IDs mirror real-world execution venues so the platform
can practice realistic smart order routing decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BrokerProfile:
    """Execution characteristics of a simulated broker."""
    broker_id: str
    name: str
    commission_bps: float
    latency_ms: int
    fill_rate: float          # probability of full fill (vs partial)
    reject_rate: float        # probability of rejection
    spread_markup_bps: float  # additional spread cost (worse price)
    sector_specializations: list[str] = field(default_factory=list)
    specialization_bonus_bps: float = 0.0  # spread improvement in specialized sectors
    max_participation_rate: float = 0.15   # max fraction of ADV per order


DEFAULT_BROKERS: dict[str, BrokerProfile] = {
    "GS": BrokerProfile(
        broker_id="GS",
        name="Goldman Sachs Execution Services",
        commission_bps=3.0,
        latency_ms=25,
        fill_rate=0.95,
        reject_rate=0.005,
        spread_markup_bps=0.5,
        sector_specializations=["Financials", "Technology"],
        specialization_bonus_bps=1.5,
        max_participation_rate=0.15,
    ),
    "JPM": BrokerProfile(
        broker_id="JPM",
        name="J.P. Morgan Execution Services",
        commission_bps=2.5,
        latency_ms=40,
        fill_rate=0.90,
        reject_rate=0.01,
        spread_markup_bps=1.0,
        sector_specializations=["Energy", "Materials", "Healthcare"],
        specialization_bonus_bps=2.0,
        max_participation_rate=0.12,
    ),
    "INST": BrokerProfile(
        broker_id="INST",
        name="Instinet (Nomura) Agency Broker",
        commission_bps=1.5,
        latency_ms=80,
        fill_rate=0.85,
        reject_rate=0.02,
        spread_markup_bps=0.0,
        sector_specializations=[],
        specialization_bonus_bps=0.0,
        max_participation_rate=0.08,
    ),
    "LQNT": BrokerProfile(
        broker_id="LQNT",
        name="Liquidnet Dark Pool",
        commission_bps=1.0,
        latency_ms=200,
        fill_rate=0.60,
        reject_rate=0.05,
        spread_markup_bps=-1.0,  # price improvement in dark pool
        sector_specializations=["Technology", "Consumer Discretionary"],
        specialization_bonus_bps=1.0,
        max_participation_rate=0.20,
    ),
}


def get_broker(broker_id: str) -> BrokerProfile | None:
    return DEFAULT_BROKERS.get(broker_id)


def get_all_brokers() -> list[BrokerProfile]:
    return list(DEFAULT_BROKERS.values())
