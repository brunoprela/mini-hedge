"""Config-driven adapter construction using a registry pattern.

Adding a new adapter = one file in app/adapters/ + one entry in the registry dict.
Zero changes to any module code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.config import Settings
    from app.modules.orders.broker_registry import BrokerRegistry
    from app.shared.adapters import (
        AltDataProvider,
        BrokerAdapter,
        CorporateActionsAdapter,
        FundAdminAdapter,
        KYCScreeningAdapter,
        LLMAdapter,
        MarketDataAdapter,
        ReferenceDataAdapter,
    )
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


def build_broker_registry(
    config: Settings,
) -> BrokerRegistry:
    """Build a BrokerRegistry with one adapter per configured broker_id.

    ``config.broker_adapters`` is a comma-separated list of
    ``BROKER_ID:adapter_type`` pairs (e.g. ``"GS:mock-exchange,JPM:mock-exchange"``).
    A single value without a colon means "one broker using that adapter type"
    (backward compat with ``broker_adapter = "in-process"``).
    """
    from app.modules.orders.broker_registry import BrokerRegistry

    registry = BrokerRegistry()
    raw = config.broker_adapters.strip()

    if ":" not in raw:
        # Legacy single-adapter mode — use broker_adapter field
        adapter = build_broker_adapter(config)
        registry.register("DEFAULT", adapter)
        return registry

    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        broker_id, adapter_type = entry.split(":", 1)
        broker_id = broker_id.strip()
        adapter_type = adapter_type.strip()

        factory_fn = _BROKER_REGISTRY.get(adapter_type)
        if factory_fn is None:
            msg = f"Unknown adapter type {adapter_type!r} for broker {broker_id}"
            raise ValueError(msg)

        adapter = factory_fn(config)
        # Set broker_id on mock-exchange adapters
        if hasattr(adapter, "_broker_id"):
            adapter._broker_id = broker_id
        registry.register(broker_id, adapter)

    return registry


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


def _build_mock_exchange_corporate_actions(
    cfg: Settings,
    **_kwargs: object,
) -> CorporateActionsAdapter:
    from app.adapters.mock_exchange_corporate_actions import MockExchangeCorporateActionsAdapter

    return MockExchangeCorporateActionsAdapter(base_url=cfg.mock_exchange_url)


def _build_mock_exchange_fund_admin(
    cfg: Settings,
    **_kwargs: object,
) -> FundAdminAdapter:
    from app.adapters.mock_exchange_fund_admin import MockExchangeFundAdminAdapter

    return MockExchangeFundAdminAdapter(base_url=cfg.mock_exchange_url)


def _build_mock_kyc_screening(
    cfg: Settings,
    **_kwargs: object,
) -> KYCScreeningAdapter:
    from app.adapters.mock_kyc_screening import MockKYCScreeningAdapter

    return MockKYCScreeningAdapter()


def _build_ollama_llm(cfg: Settings, **_kwargs: object) -> LLMAdapter:
    from app.adapters.ollama_llm import OllamaLLMAdapter

    return OllamaLLMAdapter(base_url=cfg.ollama_url, model=cfg.ollama_model)


def _build_anthropic_llm(cfg: Settings, **_kwargs: object) -> LLMAdapter:
    from app.adapters.anthropic_llm import AnthropicLLMAdapter

    return AnthropicLLMAdapter(api_key=cfg.anthropic_api_key, model=cfg.anthropic_model)


def _build_mock_llm(cfg: Settings, **_kwargs: object) -> LLMAdapter:
    from app.adapters.mock_llm import MockLLMAdapter

    return MockLLMAdapter()


def _build_mock_alt_data(cfg: Settings, **_kwargs: object) -> AltDataProvider:
    from app.adapters.mock_alt_data import MockAltDataProvider

    return MockAltDataProvider()


def _build_file_alt_data(cfg: Settings, **_kwargs: object) -> AltDataProvider:
    from app.adapters.file_alt_data import FileAltDataProvider

    return FileAltDataProvider(data_dir=cfg.alt_data_dir)


def _build_fmp_alt_data(cfg: Settings, **_kwargs: object) -> AltDataProvider:
    from app.adapters.fmp_alt_data import FMPAltDataProvider

    return FMPAltDataProvider(api_key=cfg.fmp_api_key)


# ---------------------------------------------------------------------------
#  Registries — one per adapter type
# ---------------------------------------------------------------------------

_MARKET_DATA_REGISTRY: dict[str, Callable[..., MarketDataAdapter]] = {
    "mock-exchange": _build_mock_exchange_market_data,
}

_BROKER_REGISTRY: dict[str, Callable[..., BrokerAdapter]] = {
    "mock-exchange": _build_mock_exchange_broker,
    "in-process": _build_in_process_broker,
    # Future: "fix": _build_fix_broker,
    # Future: "bloomberg": _build_bloomberg_broker,
    # Future: "ib": _build_ib_broker,
}

_REFERENCE_DATA_REGISTRY: dict[str, Callable[..., ReferenceDataAdapter]] = {
    "mock-exchange": _build_mock_exchange_reference_data,
    "seed": _build_seed_reference_data,
}

_CORPORATE_ACTIONS_REGISTRY: dict[str, Callable[..., CorporateActionsAdapter]] = {
    "mock-exchange": _build_mock_exchange_corporate_actions,
}

_FUND_ADMIN_REGISTRY: dict[str, Callable[..., FundAdminAdapter]] = {
    "mock-exchange": _build_mock_exchange_fund_admin,
}

_KYC_SCREENING_REGISTRY: dict[str, Callable[..., KYCScreeningAdapter]] = {
    "mock-kyc": _build_mock_kyc_screening,
}

_LLM_REGISTRY: dict[str, Callable[..., LLMAdapter]] = {
    "ollama": _build_ollama_llm,
    "anthropic": _build_anthropic_llm,
    "mock": _build_mock_llm,
}

_ALT_DATA_REGISTRY: dict[str, Callable[..., AltDataProvider]] = {
    "mock": _build_mock_alt_data,
    "file": _build_file_alt_data,
    "fmp": _build_fmp_alt_data,
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
    return factory(config, event_bus=event_bus)


def build_broker_adapter(config: Settings) -> BrokerAdapter:
    factory = _BROKER_REGISTRY.get(config.broker_adapter)
    if factory is None:
        msg = (
            f"Unknown broker_adapter: {config.broker_adapter!r}. "
            f"Available: {sorted(_BROKER_REGISTRY)}"
        )
        raise ValueError(msg)
    return factory(config)


def build_reference_data_adapter(config: Settings) -> ReferenceDataAdapter:
    factory = _REFERENCE_DATA_REGISTRY.get(config.reference_data_source)
    if factory is None:
        msg = (
            f"Unknown reference_data_source: {config.reference_data_source!r}. "
            f"Available: {sorted(_REFERENCE_DATA_REGISTRY)}"
        )
        raise ValueError(msg)
    return factory(config)


def build_fund_admin_adapter(config: Settings) -> FundAdminAdapter:
    source = getattr(config, "fund_admin_source", "mock-exchange")
    factory = _FUND_ADMIN_REGISTRY.get(source)
    if factory is None:
        msg = f"Unknown fund_admin_source: {source!r}. Available: {sorted(_FUND_ADMIN_REGISTRY)}"
        raise ValueError(msg)
    return factory(config)


def build_kyc_screening_adapter(config: Settings) -> KYCScreeningAdapter:
    source = getattr(config, "kyc_screening_source", "mock-kyc")
    factory = _KYC_SCREENING_REGISTRY.get(source)
    if factory is None:
        msg = (
            f"Unknown kyc_screening_source: {source!r}. "
            f"Available: {sorted(_KYC_SCREENING_REGISTRY)}"
        )
        raise ValueError(msg)
    return factory(config)


def build_corporate_actions_adapter(
    config: Settings,
) -> CorporateActionsAdapter:
    source = config.corporate_actions_source
    factory = _CORPORATE_ACTIONS_REGISTRY.get(source)
    if factory is None:
        msg = (
            f"Unknown corporate_actions_source: {source!r}. "
            f"Available: {sorted(_CORPORATE_ACTIONS_REGISTRY)}"
        )
        raise ValueError(msg)
    return factory(config)


def build_llm_adapter(config: Settings) -> LLMAdapter:
    factory = _LLM_REGISTRY.get(config.llm_adapter)
    if factory is None:
        msg = f"Unknown llm_adapter: {config.llm_adapter!r}. Available: {sorted(_LLM_REGISTRY)}"
        raise ValueError(msg)
    return factory(config)


def build_alt_data_provider(config: Settings) -> AltDataProvider:
    factory = _ALT_DATA_REGISTRY.get(config.alt_data_provider)
    if factory is None:
        msg = (
            f"Unknown alt_data_provider: {config.alt_data_provider!r}. "
            f"Available: {sorted(_ALT_DATA_REGISTRY)}"
        )
        raise ValueError(msg)
    return factory(config)
