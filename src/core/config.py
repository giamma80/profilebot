"""Centralized application settings for ProfileBot."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )

    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    availability_cache_ttl: int = Field(
        default=3600,
        validation_alias="AVAILABILITY_CACHE_TTL",
    )
    availability_refresh_csv_path: str | None = Field(
        default=None,
        validation_alias="AVAILABILITY_REFRESH_CSV_PATH",
    )
    availability_refresh_schedule: str = Field(
        default="0 * * * *",
        validation_alias="AVAILABILITY_REFRESH_SCHEDULE",
    )
    celery_broker_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="CELERY_BROKER_URL",
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="CELERY_RESULT_BACKEND",
    )
    celery_result_expires: int = Field(
        default=86400,
        validation_alias="CELERY_RESULT_EXPIRES",
    )
    celery_worker_concurrency: int = Field(
        default=4,
        validation_alias="CELERY_WORKER_CONCURRENCY",
    )
    celery_task_time_limit: int = Field(
        default=300,
        validation_alias="CELERY_TASK_TIME_LIMIT",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
