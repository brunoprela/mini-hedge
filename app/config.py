from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+asyncpg://minihedge:minihedge@localhost:5433/minihedge"
    database_pool_size: int = 10
    database_max_overflow: int = 5

    app_env: str = "local"
    log_level: str = "DEBUG"

    simulator_interval_ms: int = 1000
    simulator_enabled: bool = True

    jwt_secret: str = "minihedge-dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60

    fga_api_url: str = "http://localhost:8080"
    fga_store_name: str = "minihedge"
    fga_enabled: bool = True


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
