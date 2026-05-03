from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://ims_user:ims_pass@localhost:5432/ims_db"
    mongodb_url: str = "mongodb://ims_user:ims_pass@localhost:27017/ims_signals?authSource=admin"
    redis_url: str = "redis://localhost:6379/0"
    environment: str = "development"

    # Queue & rate limiting
    queue_max_size: int = 50_000
    rate_limit_per_second: int = 10_000
    debounce_window_seconds: int = 10
    debounce_threshold: int = 100

    # Observability
    metrics_interval_seconds: int = 5

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
