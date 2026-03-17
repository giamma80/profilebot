from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import redis

from src.services.ingestion.status_service import (
    IngestionStatusError,
    IngestionStatusService,
)


class DummyRedis:
    def __init__(self, value: str | None) -> None:
        self.value = value

    def get(self, _key: str) -> str | None:
        return self.value


class DummyFreshnessGate:
    def __init__(self, *, is_fresh: bool) -> None:
        self._is_fresh = is_fresh

    def is_fresh(self, _res_id: int) -> bool:
        return self._is_fresh


def test_get_status__redis_available_with_timestamp() -> None:
    last_run = datetime.now(UTC) - timedelta(seconds=120)
    service = IngestionStatusService(
        redis_client=DummyRedis(last_run.isoformat()),
        freshness_gate=DummyFreshnessGate(is_fresh=True),
    )

    result = service.get_status(10)

    assert result.res_id == 10
    assert result.last_ingested_at is not None
    assert result.is_fresh is True
    assert result.staleness_seconds is not None
    assert 0 <= result.staleness_seconds <= 300


def test_get_status__redis_available_without_timestamp() -> None:
    service = IngestionStatusService(
        redis_client=DummyRedis(None),
        freshness_gate=DummyFreshnessGate(is_fresh=False),
    )

    result = service.get_status(10)

    assert result.res_id == 10
    assert result.last_ingested_at is None
    assert result.is_fresh is False
    assert result.staleness_seconds is None


def test_get_status__redis_unavailable_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_args, **_kwargs) -> redis.Redis:
        raise redis.RedisError("boom")

    monkeypatch.setattr(redis, "from_url", _raise)

    service = IngestionStatusService()

    with pytest.raises(IngestionStatusError, match="Redis unavailable"):
        service.get_status(10)
