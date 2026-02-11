from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import redis

from src.services.availability.cache import AvailabilityCache
from src.services.availability.schemas import AvailabilityStatus, ProfileAvailability


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

    def scan(self, cursor: int, match: str, count: int) -> tuple[int, list[str]]:
        prefix = match.replace("*", "")
        keys = [key for key in self._store if key.startswith(prefix)]
        return 0, keys

    def ping(self) -> bool:
        return True


def _record(res_id: int, status: AvailabilityStatus, allocation_pct: int) -> ProfileAvailability:
    return ProfileAvailability(
        res_id=res_id,
        status=status,
        allocation_pct=allocation_pct,
        current_project=None,
        available_from=None,
        updated_at=datetime(2026, 2, 10, 8, 0, 0, tzinfo=UTC),
    )


def test_cache_set_and_get_roundtrip() -> None:
    client = FakeRedis()
    cache = AvailabilityCache(client=cast(redis.Redis[Any], client), ttl_seconds=1800)

    record = _record(100, AvailabilityStatus.FREE, 0)
    cache.set(record)

    stored = cache.get(100)

    assert stored is not None
    assert stored.res_id == 100
    assert stored.status == AvailabilityStatus.FREE


def test_cache_get_missing_returns_none() -> None:
    cache = AvailabilityCache(client=cast(redis.Redis[Any], FakeRedis()), ttl_seconds=1800)

    assert cache.get(999) is None


def test_cache_set_many_and_get_many() -> None:
    client = FakeRedis()
    cache = AvailabilityCache(client=cast(redis.Redis[Any], client), ttl_seconds=1800)

    cache.set_many(
        [
            _record(100, AvailabilityStatus.FREE, 0),
            _record(200, AvailabilityStatus.PARTIAL, 40),
        ]
    )

    results = cache.get_many([100, 200, 300])

    assert set(results.keys()) == {100, 200}
    assert results[100].status == AvailabilityStatus.FREE
    assert results[200].status == AvailabilityStatus.PARTIAL


def test_cache_scan_records_returns_all() -> None:
    client = FakeRedis()
    cache = AvailabilityCache(client=cast(redis.Redis[Any], client), ttl_seconds=1800)

    cache.set_many(
        [
            _record(100, AvailabilityStatus.FREE, 0),
            _record(200, AvailabilityStatus.BUSY, 100),
        ]
    )

    records = cache.scan_records()

    assert sorted([record.res_id for record in records]) == [100, 200]


def test_cache_invalidate_removes_key() -> None:
    client = FakeRedis()
    cache = AvailabilityCache(client=cast(redis.Redis[Any], client), ttl_seconds=1800)

    cache.set(_record(100, AvailabilityStatus.FREE, 0))
    cache.invalidate(100)

    assert cache.get(100) is None


def test_cache_touch_updates_expiration() -> None:
    client = FakeRedis()
    cache = AvailabilityCache(client=cast(redis.Redis[Any], client), ttl_seconds=1800)

    cache.set(_record(100, AvailabilityStatus.FREE, 0))
    cache.touch(100)

    key = "profilebot:availability:100"
    assert client._expirations[key] == 1800


def test_cache_ping_returns_true() -> None:
    cache = AvailabilityCache(client=cast(redis.Redis[Any], FakeRedis()), ttl_seconds=1800)

    assert cache.ping() is True
