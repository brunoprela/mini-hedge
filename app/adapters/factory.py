"""Config-driven adapter construction using a registry pattern.

Adding a new adapter = one file in app/adapters/ + one entry in the registry dict.
Zero changes to any module code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings
    from app.shared.adapters import BrokerAdapter, MarketDataAdapter, ReferenceDataAdapter
    from app.shared.events import EventBus


# ---------------------------------------------------------------------------
#  Lazy imports — concrete adapters are only imported when selected
# ---------------------------------------------------------------------------


def _build_mock_exchange_market_data(
    cfg: Settings,
    *,
    event_bus: EventBus | None = None,
) -> MarketDataAdapter:
    from app.adapters.mock_exchange_market_data import MockExchangeMarketDataAdapter

    if event_bus is None:
        msg = "mock-exchange market data adapter requires event_bus"
        raise ValueError(msg)
    return MockExchangeMarketDataAdapter(
        base_url=cfg.mock_exchange_url,
        kafka_bootstrap_servers=cfg.mock_exchange_kafka_bootstrap_servers,
        event_bus=event_bus,
    )


def _build_mock_exchange_broker(
    cfg: Settings,
    **_kwargs: object,
) -> BrokerAdapter:
    from app.adapters.mock_exchange_broker import MockExchangeBrokerAdapter

    return MockExchangeBrokerAdapter(
        base_url=cfg.mock_exchange_url,
        kafka_bootstrap_servers=cfg.mock_exchange_kafka_bootstrap_servers,
    )


def _build_in_process_broker(cfg: Settings, **_kwargs: object) -> BrokerAdapter:
    from app.adapters.in_process_broker import InProcessBrokerAdapter

    return InProcessBrokerAdapter()


def _build_mock_exchange_reference_data(
    cfg: Settings,
    **_kwargs: object,
) -> ReferenceDataAdapter:
    from app.adapters.mock_exchange_reference_data import MockExchangeReferenceDataAdapter

    return MockExchangeReferenceDataAdapter(base_url=cfg.mock_exchange_url)


def _build_seed_reference_data(cfg: Settings, **_kwargs: object) -> ReferenceDataAdapter:
    from app.adapters.seed_reference_data import SeedReferenceDataAdapter

    return SeedReferenceDataAdapter()


# ---------------------------------------------------------------------------
#  Registries — one per adapter type
# ---------------------------------------------------------------------------

_MARKET_DATA_REGISTRY: dict[str, type[object] | object] = {
    "mock-exchange": _build_mock_exchange_market_data,
}

_BROKER_REGISTRY: dict[str, type[object] | object] = {
    "mock-exchange": _build_mock_exchange_broker,
    "in-process": _build_in_process_broker,
    # Future: "fix": _build_fix_broker,
    # Future: "bloomberg": _build_bloomberg_broker,
    # Future: "ib": _build_ib_broker,
}

_REFERENCE_DATA_REGISTRY: dict[str, type[object] | object] = {
    "mock-exchange": _build_mock_exchange_reference_data,
    "seed": _build_seed_reference_data,
}


# ---------------------------------------------------------------------------
#  Public factory functions
# ---------------------------------------------------------------------------


def build_market_data_adapter(
    config: Settings,
    *,
    event_bus: EventBus | None = None,
) -> MarketDataAdapter:
    factory = _MARKET_DATA_REGISTRY.get(config.market_data_source)
    if factory is None:
        msg = (
            f"Unknown market_data_source: {config.market_data_source!r}. "
            f"Available: {sorted(_MARKET_DATA_REGISTRY)}"
        )
        raise ValueError(msg)
    return factory(config, event_bus=event_bus)  # type: ignore[operator]


def build_broker_adapter(config: Settings) -> BrokerAdapter:
    factory = _BROKER_REGISTRY.get(config.broker_adapter)
    if factory is None:
        msg = (
            f"Unknown broker_adapter: {config.broker_adapter!r}. "
            f"Available: {sorted(_BROKER_REGISTRY)}"
        )
        raise ValueError(msg)
    return factory(config)  # type: ignore[operator]


def build_reference_data_adapter(config: Settings) -> ReferenceDataAdapter:
    factory = _REFERENCE_DATA_REGISTRY.get(config.reference_data_source)
    if factory is None:
        msg = (
            f"Unknown reference_data_source: {config.reference_data_source!r}. "
            f"Available: {sorted(_REFERENCE_DATA_REGISTRY)}"
        )
        raise ValueError(msg)
    return factory(config)  # type: ignore[operator]
