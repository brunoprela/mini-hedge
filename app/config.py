from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_JWT_SECRET = "minihedge-dev-secret-change-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    vault_addr: str = ""
    vault_token: str = ""

    database_url: str = "postgresql+asyncpg://minihedge:minihedge@localhost:5433/minihedge"
    database_read_url: str = ""
    database_pool_size: int = 20
    database_max_overflow: int = 10
    database_pool_timeout: int = 30

    app_env: str = "local"
    log_level: str = "INFO"

    jwt_secret: str = _DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60

    fga_api_url: str = "http://localhost:8080"
    fga_store_name: str = "minihedge"
    fga_enabled: bool = True

    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_schema_registry_url: str = "http://localhost:8081"
    kafka_replication_factor: int = 1  # 3 for production
    kafka_num_partitions: int = 3

    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = False

    otel_enabled: bool = False
    otel_endpoint: str = "http://localhost:4317"

    immudb_enabled: bool = False
    immudb_host: str = "localhost"
    immudb_port: int = 3322
    immudb_username: str = "immudb"
    immudb_password: str = "immudb"
    immudb_database: str = "defaultdb"

    opensearch_enabled: bool = False
    opensearch_host: str = "localhost"
    opensearch_port: int = 9200
    opensearch_username: str = "admin"
    opensearch_password: str = "admin"

    minio_enabled: bool = False
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"

    temporal_enabled: bool = False
    temporal_host: str = "localhost"
    temporal_port: int = 7233

    # Adapter configuration — controls which external data sources the platform uses
    mock_exchange_url: str = "http://localhost:8100"
    mock_exchange_kafka_bootstrap_servers: str = "localhost:9192"
    market_data_source: str = "mock-exchange"  # "mock-exchange"
    broker_adapter: str = "in-process"  # "mock-exchange" | "in-process" | "fix"
    reference_data_source: str = "seed"  # "mock-exchange" | "seed"
    seed_on_startup: bool = True  # set to False to start with an empty platform
    corporate_actions_source: str = "mock-exchange"  # "mock-exchange"
    broker_adapters: str = ""  # "GS:mock-exchange,JPM:mock-exchange" or empty for single
    routing_split_threshold: int = 50000
    fix_host: str = "localhost"
    fix_port: int = 9878

    # LLM adapter configuration
    llm_adapter: str = "ollama"  # "ollama" | "anthropic" | "mock"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # Alternative data configuration
    alt_data_provider: str = "mock"  # "mock" | "file" | "fmp"
    alt_data_dir: str = "data/alt"  # for file provider
    fmp_api_key: str = ""  # for FMP provider

    keycloak_url: str = "http://localhost:8180"
    # Browser-facing URL for issuer validation; defaults to keycloak_url
    keycloak_browser_url: str = ""
    keycloak_realm: str = "minihedge"
    keycloak_client_id: str = "mini-hedge-ui"

    keycloak_ops_realm: str = "minihedge-ops"
    keycloak_ops_client_id: str = "mini-hedge-ops-ui"

    # Per-customer Keycloak realm mapping.
    # JSON string: {"customer-id": {"realm": "realm-name", "client_id": "client-id"}}
    # When a customer is not in the map, the default keycloak_realm is used.
    keycloak_customer_realms: str = "{}"

    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3100",
    ]

    @model_validator(mode="after")
    def _reject_dev_secret_in_production(self) -> Settings:
        if self.app_env not in ("local", "test") and self.jwt_secret == _DEV_JWT_SECRET:
            raise ValueError(
                "JWT_SECRET must be set to a unique value in non-local environments. "
                "The default dev secret is not allowed."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()

    # Overlay secrets from Vault if configured
    if settings.vault_addr:
        from app.shared.vault import load_vault_secrets

        vault_secrets = load_vault_secrets(
            vault_addr=settings.vault_addr,
            vault_token=settings.vault_token,
        )
        if vault_secrets:
            # Only override fields that exist in Settings
            for key, value in vault_secrets.items():
                if hasattr(settings, key) and value:
                    object.__setattr__(settings, key, value)

    return settings
