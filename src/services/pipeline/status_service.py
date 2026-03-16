"""Pipeline status service that aggregates Celery/Redis/Qdrant metrics."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol, cast

import redis
from celery import Celery
from qdrant_client import QdrantClient

from src.core.config import get_settings
from src.services.embedding.celery_app import celery_app as default_celery_app
from src.services.pipeline.schemas import PipelineStatusResponse
from src.services.qdrant.client import get_qdrant_client

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_NAME = "celery"
DEFAULT_COLLECTION_NAME = "cv_skills"
DEFAULT_INSPECT_TIMEOUT = 3.0
PIPELINE_FAILED_COUNT_KEY = "pipeline:failed_count"
PIPELINE_LAST_RUN_AT_KEY = "pipeline:last_run_at"
TOTAL_SOURCES = 3
StatusLiteral = Literal["healthy", "degraded", "error"]


class RedisClient(Protocol):
    def llen(self, key: str) -> int: ...

    def get(self, key: str) -> str | None: ...


class CountResult(Protocol):
    count: int


@dataclass(frozen=True)
class PipelineStatusConfig:
    queue_name: str = DEFAULT_QUEUE_NAME
    collection_name: str = DEFAULT_COLLECTION_NAME
    inspect_timeout: float = DEFAULT_INSPECT_TIMEOUT


@dataclass(frozen=True)
class PipelineStatusResult:
    """Internal container for pipeline status responses."""

    response: PipelineStatusResponse
    failed_sources: int


class PipelineStatusService:
    """Service that aggregates pipeline status signals."""

    def __init__(
        self,
        qdrant_client: QdrantClient | None = None,
        redis_client: RedisClient | None = None,
        celery_app: Celery | None = None,
        *,
        config: PipelineStatusConfig | None = None,
    ) -> None:
        settings = get_settings()
        resolved_config = config or PipelineStatusConfig()
        self._qdrant_client = qdrant_client or get_qdrant_client()
        self._celery_app = celery_app or default_celery_app
        self._queue_name = resolved_config.queue_name
        self._collection_name = resolved_config.collection_name
        self._inspect_timeout = resolved_config.inspect_timeout
        self._redis_client: RedisClient | None

        if redis_client is not None:
            self._redis_client = redis_client
        else:
            try:
                self._redis_client = redis.from_url(
                    settings.celery_broker_url,
                    decode_responses=True,
                )
            except (redis.RedisError, ValueError) as exc:
                logger.warning("Redis client initialization failed: %s", exc)
                self._redis_client = None

    def get_status(self) -> PipelineStatusResult:
        """Return a snapshot of the pipeline status from live sources."""
        warnings: list[str] = []
        failed_sources, failed_count, last_run_at = 0, 0, None
        indexed_count: int = 0

        try:
            count_result = self._qdrant_client.count(
                collection_name=self._collection_name,
            )
            if isinstance(count_result, int):
                indexed_count = count_result
            else:
                indexed_count = cast(CountResult, count_result).count
        except Exception as exc:  # pragma: no cover - defensive for external client
            logger.warning("Qdrant count failed: %s", exc)
            warnings.append("Qdrant unavailable")
            failed_sources += 1

        if self._redis_client is None:
            warnings.append("Redis unavailable")
            queued_count = 0
            failed_sources += 1
        else:
            try:
                queued_count = int(self._redis_client.llen(self._queue_name))
            except redis.RedisError as exc:
                logger.warning("Redis queue length failed: %s", exc)
                warnings.append("Redis unavailable")
                queued_count = 0
                failed_sources += 1
            else:
                try:
                    failed_raw = self._redis_client.get(PIPELINE_FAILED_COUNT_KEY)
                    failed_count = int(failed_raw) if failed_raw is not None else 0
                    last_run_raw = self._redis_client.get(PIPELINE_LAST_RUN_AT_KEY)
                    if last_run_raw:
                        last_run_at = datetime.fromisoformat(last_run_raw)
                except (ValueError, redis.RedisError) as exc:
                    logger.warning("Redis pipeline metadata failed: %s", exc)
                    warnings.append("Redis metadata unavailable")

        try:
            inspect = self._celery_app.control.inspect(timeout=self._inspect_timeout)
            active = inspect.active() if inspect else None
            if active is None:
                raise RuntimeError("Celery inspect unavailable")
            active_count = sum(len(tasks or []) for tasks in active.values()) if active else 0
        except Exception as exc:  # pragma: no cover - defensive for external client
            logger.warning("Celery inspect failed: %s", exc)
            warnings.append("Celery unavailable")
            active_count = 0
            failed_sources += 1

        status = _resolve_status(failed_sources)

        response = PipelineStatusResponse(
            indexed_count=indexed_count,
            queued_count=queued_count,
            active_count=active_count,
            failed_count=failed_count,
            status=status,
            warnings=warnings,
            last_run_at=last_run_at,
            last_checked=datetime.now(UTC),
        )
        return PipelineStatusResult(response=response, failed_sources=failed_sources)


def _resolve_status(failed_sources: int) -> StatusLiteral:
    if failed_sources == 0:
        return "healthy"
    if failed_sources >= TOTAL_SOURCES:
        return "error"
    return "degraded"


__all__ = ["PipelineStatusConfig", "PipelineStatusResult", "PipelineStatusService"]
