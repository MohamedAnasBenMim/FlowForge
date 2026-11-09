from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./flowforge.db"
    redis_url: str = "redis://localhost:6379/0"
    queue_name: str = "flowforge:executions"
    retry_base_seconds: float = 1.0
    max_attempts: int = 3

    model_config = SettingsConfigDict(env_file=".env", env_prefix="FLOWFORGE_")


@lru_cache
def get_settings() -> Settings:
    return Settings()
