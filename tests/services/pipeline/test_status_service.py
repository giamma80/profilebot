from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import redis

from src.services.pipeline.status_service import PipelineStatusService


class FakeCountResult:
    def __init__(self, count: int) -> None:
        self.count = count


class FakeQdrantClient:
    def __init__(self, count: int, error: Exception | None = None) -> None:
        self._count = count
        self._error = error

    def count(self, *, collection_name: str) -> FakeCountResult:
        if self._error:
            raise self._error
        return FakeCountResult(self._count)


class FakeRedisClient:
    def __init__(
        self,
        queued: int,
        *,
        failed_count: int = 0,
        last_run_at: str | None = None,
        error: Exception | None = None,
    ) -> None:
        self._queued = queued
        self._failed_count = failed_count
        self._last_run_at = last_run_at
        self._error = error

    def llen(self, _key: str) -> int:
        if self._error:
            raise self._error
        return self._queued

    def get(self, key: str) -> str | None:
        if self._error:
            raise self._error
        if key == "pipeline:failed_count":
            return str(self._failed_count)
        if key == "pipeline:last_run_at":
            return self._last_run_at
        return None


class FakeInspect:
    def __init__(
        self,
        active: dict[str, list[dict[str, Any]]] | None,
        error: Exception | None = None,
    ) -> None:
        self._active = active
        self._error = error

    def active(self) -> dict[str, list[dict[str, Any]]] | None:
        if self._error:
            raise self._error
        return self._active


class FakeControl:
    def __init__(self, inspect: FakeInspect | None) -> None:
        self._inspect = inspect

    def inspect(self, timeout: float | None = None) -> FakeInspect | None:
        return self._inspect


class FakeCeleryApp:
    def __init__(self, inspect: FakeInspect | None) -> None:
        self.control = FakeControl(inspect)


def test_get_status__all_sources_ok__returns_healthy() -> None:
    expected_last_run_at = datetime(2026, 3, 1, 9, 30, tzinfo=UTC)
    service = PipelineStatusService(
        qdrant_client=FakeQdrantClient(120),
        redis_client=FakeRedisClient(
            5,
            failed_count=2,
            last_run_at=expected_last_run_at.isoformat(),
        ),
        celery_app=FakeCeleryApp(
            FakeInspect(
                {
                    "worker-1": [{"id": "task-1"}, {"id": "task-2"}],
                    "worker-2": [],
                }
            )
        ),
    )

    result = service.get_status()

    assert result.failed_sources == 0
    assert result.response.indexed_count == 120
    assert result.response.queued_count == 5
    assert result.response.active_count == 2
    assert result.response.failed_count == 2
    assert result.response.last_run_at == expected_last_run_at
    assert result.response.status == "healthy"
    assert result.response.warnings == []


def test_get_status__qdrant_down__returns_degraded() -> None:
    service = PipelineStatusService(
        qdrant_client=FakeQdrantClient(0, error=RuntimeError("down")),
        redis_client=FakeRedisClient(3),
        celery_app=FakeCeleryApp(FakeInspect({"worker-1": []})),
    )

    result = service.get_status()

    assert result.failed_sources == 1
    assert result.response.indexed_count == 0
    assert result.response.status == "degraded"
    assert "Qdrant unavailable" in result.response.warnings


def test_get_status__redis_down__returns_degraded() -> None:
    service = PipelineStatusService(
        qdrant_client=FakeQdrantClient(7),
        redis_client=FakeRedisClient(0, error=redis.RedisError("down")),
        celery_app=FakeCeleryApp(FakeInspect({"worker-1": []})),
    )

    result = service.get_status()

    assert result.failed_sources == 1
    assert result.response.queued_count == 0
    assert result.response.status == "degraded"
    assert "Redis unavailable" in result.response.warnings


def test_get_status__celery_unavailable__returns_degraded() -> None:
    service = PipelineStatusService(
        qdrant_client=FakeQdrantClient(7),
        redis_client=FakeRedisClient(2),
        celery_app=FakeCeleryApp(None),
    )

    result = service.get_status()

    assert result.failed_sources == 1
    assert result.response.active_count == 0
    assert result.response.status == "degraded"
    assert "Celery unavailable" in result.response.warnings


def test_get_status__all_sources_down__returns_error() -> None:
    service = PipelineStatusService(
        qdrant_client=FakeQdrantClient(0, error=RuntimeError("down")),
        redis_client=FakeRedisClient(0, error=redis.RedisError("down")),
        celery_app=FakeCeleryApp(FakeInspect(None)),
    )

    result = service.get_status()

    assert result.failed_sources == 3
    assert result.response.indexed_count == 0
    assert result.response.queued_count == 0
    assert result.response.active_count == 0
    assert result.response.status == "error"
    assert set(result.response.warnings) == {
        "Qdrant unavailable",
        "Redis unavailable",
        "Celery unavailable",
    }
