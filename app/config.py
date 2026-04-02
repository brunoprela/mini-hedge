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
    simulator_enabled: bool = True

    jwt_secret: str = _DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60

    fga_api_url: str = "http://localhost:8080"
    fga_store_name: str = "minihedge"
    fga_enabled: bool = True

    keycloak_url: str = "http://localhost:8180"
    keycloak_browser_url: str = ""  # Browser-facing URL for issuer validation; defaults to keycloak_url
    keycloak_realm: str = "minihedge"
    keycloak_client_id: str = "mini-hedge-ui"

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
