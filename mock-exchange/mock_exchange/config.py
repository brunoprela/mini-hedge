from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_schema_registry_url: str = "http://localhost:8081"

    simulator_enabled: bool = True
    simulator_interval_ms: int = 1000

    # Ambient flow — generates synthetic market activity for realistic volume
    ambient_flow_enabled: bool = True
    ambient_flow_interval_ms: int = 1000

    # Market impact model calibration
    market_impact_eta: float = 0.6

    # Trading hours enforcement — reject orders outside exchange hours
    trading_hours_enabled: bool = True

    log_level: str = "DEBUG"


settings = Settings()
