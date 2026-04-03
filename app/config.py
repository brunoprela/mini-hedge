from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_JWT_SECRET = "minihedge-dev-secret-change-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+asyncpg://minihedge:minihedge@localhost:5433/minihedge"
    database_pool_size: int = 10
    database_max_overflow: int = 5

    app_env: str = "local"
    log_level: str = "DEBUG"

    simulator_interval_ms: int = 1000
    simulator_enabled: bool = False

    jwt_secret: str = _DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60

    fga_api_url: str = "http://localhost:8080"
    fga_store_name: str = "minihedge"
    fga_enabled: bool = True

    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_schema_registry_url: str = "http://localhost:8081"

    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = False

    keycloak_url: str = "http://localhost:8180"
    # Browser-facing URL for issuer validation; defaults to keycloak_url
    keycloak_browser_url: str = ""
    keycloak_realm: str = "minihedge"
    keycloak_client_id: str = "mini-hedge-ui"

    keycloak_ops_realm: str = "minihedge-ops"
    keycloak_ops_client_id: str = "mini-hedge-ops-ui"

    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3100",
    ]

    @model_validator(mode="after")
    def _reject_dev_secret_in_production(self) -> "Settings":
        if self.app_env not in ("local", "test") and self.jwt_secret == _DEV_JWT_SECRET:
            raise ValueError(
                "JWT_SECRET must be set to a unique value in non-local environments. "
                "The default dev secret is not allowed."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
