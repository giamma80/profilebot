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
    availability_refresh_schedule: str = Field(
        default="0 * * * *",
        validation_alias="AVAILABILITY_REFRESH_SCHEDULE",
    )
    reskilling_cache_ttl: int = Field(
        default=3600,
        validation_alias="RESKILLING_CACHE_TTL",
    )
    reskilling_refresh_schedule: str = Field(
        default="*/30 * * * *",
        validation_alias="RESKILLING_REFRESH_SCHEDULE",
    )
    freshness_ttl_seconds: int = Field(
        default=43200,
        validation_alias="FRESHNESS_TTL_SECONDS",
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
    best_effort_chord_max_wait_seconds: int = Field(
        default=300,
        validation_alias="BEST_EFFORT_CHORD_MAX_WAIT_SECONDS",
    )
    ingestion_api_base_url: str = Field(
        default="http://localhost:8000",
        validation_alias="INGESTION_API_BASE_URL",
    )
    scraper_base_url: str = Field(
        default="",
        validation_alias="SCRAPER_BASE_URL",
    )
    scraper_timeout: float = Field(
        default=300.0,
        validation_alias="SCRAPER_TIMEOUT",
    )
    scraper_workflow_path: str = Field(
        default="config/workflows/res_id_workflow.yaml",
        validation_alias="SCRAPER_WORKFLOW_PATH",
    )
    llm_provider: str = Field(default="openai", validation_alias="LLM_PROVIDER")
    llm_model: str = Field(default="gpt-4", validation_alias="LLM_MODEL")
    llm_base_url: str | None = Field(default=None, validation_alias="LLM_BASE_URL")
    llm_api_key: str | None = Field(default=None, validation_alias="LLM_API_KEY")
    llm_api_version: str | None = Field(default=None, validation_alias="LLM_API_VERSION")
    llm_temperature: float = Field(default=0.1, validation_alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=2000, validation_alias="LLM_MAX_TOKENS")
    llm_timeout: float = Field(default=30.0, validation_alias="LLM_TIMEOUT")
    llm_section_classification_enabled: bool = Field(
        default=False,
        validation_alias="LLM_SECTION_CLASSIFICATION_ENABLED",
    )
    search_min_skill_score: float = Field(default=0.0, validation_alias="SEARCH_MIN_SKILL_SCORE")
    search_fallback_enabled: bool = Field(default=True, validation_alias="SEARCH_FALLBACK_ENABLED")
    search_chunk_weight: float = Field(default=0.3, validation_alias="SEARCH_CHUNK_WEIGHT")
    scoring_use_weighted: bool = Field(default=False, validation_alias="SCORING_USE_WEIGHTED")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
