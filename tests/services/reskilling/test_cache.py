from __future__ import annotations

from typing import cast

import redis

from src.services.reskilling.cache import ReskillingCache
from src.services.reskilling.schemas import ReskillingRecord, ReskillingStatus


class FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._expirations: dict[str, int] = {}

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def mget(self, keys: list[str]) -> list[str | None]:
        return [self._store.get(key) for key in keys]

    def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value
        self._expirations[key] = ttl

    def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self._expirations.pop(key, None)

    def exists(self, key: str) -> int:
        return 1 if key in self._store else 0

    def expire(self, key: str, ttl: int) -> None:
        if key in self._store:
            self._expirations[key] = ttl

    def ping(self) -> bool:
        return True


def _record(res_id: int, status: ReskillingStatus) -> ReskillingRecord:
    return ReskillingRecord(
        res_id=res_id,
        course_name="Kubernetes Fundamentals",
        skill_target="kubernetes",
        status=status,
        start_date=None,
        end_date=None,
        provider=None,
        completion_pct=75,
    )


def test_cache_set_and_get_roundtrip() -> None:
    client = FakeRedis()
    cache = ReskillingCache(client=cast(redis.Redis, client), ttl_seconds=1800)

    record = _record(100, ReskillingStatus.IN_PROGRESS)
    cache.set(record)

    stored = cache.get(100)

    assert stored is not None
    assert stored.res_id == 100
    assert stored.status == ReskillingStatus.IN_PROGRESS


def test_cache_get_missing_returns_none() -> None:
    cache = ReskillingCache(client=cast(redis.Redis, FakeRedis()), ttl_seconds=1800)

    assert cache.get(999) is None


def test_cache_set_many_and_get_many() -> None:
    client = FakeRedis()
    cache = ReskillingCache(client=cast(redis.Redis, client), ttl_seconds=1800)

    cache.set_many(
        [
            _record(100, ReskillingStatus.IN_PROGRESS),
            _record(200, ReskillingStatus.COMPLETED),
        ]
    )

    results = cache.get_many([100, 200, 300])

    assert set(results.keys()) == {100, 200}
    assert results[100].status == ReskillingStatus.IN_PROGRESS
    assert results[200].status == ReskillingStatus.COMPLETED


def test_cache_invalidate_removes_key() -> None:
    client = FakeRedis()
    cache = ReskillingCache(client=cast(redis.Redis, client), ttl_seconds=1800)

    cache.set(_record(100, ReskillingStatus.IN_PROGRESS))
    cache.invalidate(100)

    assert cache.get(100) is None


def test_cache_touch_updates_expiration() -> None:
    client = FakeRedis()
    cache = ReskillingCache(client=cast(redis.Redis, client), ttl_seconds=1800)

    cache.set(_record(100, ReskillingStatus.IN_PROGRESS))
    cache.touch(100)

    key = "profilebot:reskilling:100"
    assert client._expirations[key] == 1800


def test_cache_ping_returns_true() -> None:
    cache = ReskillingCache(client=cast(redis.Redis, FakeRedis()), ttl_seconds=1800)

    assert cache.ping() is True
