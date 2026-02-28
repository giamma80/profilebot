from __future__ import annotations

from typing import Any, cast

import redis

from src.services.reskilling.cache import ReskillingCache
from src.services.reskilling.schemas import ReskillingRecord, ReskillingStatus
from src.services.reskilling.service import ReskillingService
from src.services.scraper.client import ScraperClient


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


class FakeScraperClient:
    def __init__(self, payloads: dict[int, dict[str, Any]], calls: list[int]) -> None:
        self._payloads = payloads
        self._calls = calls

    def __enter__(self) -> FakeScraperClient:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def fetch_reskilling_row(self, res_id: int) -> dict[str, Any]:
        self._calls.append(res_id)
        return self._payloads[res_id]


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


def _payload(res_id: int, status: str) -> dict[str, Any]:
    return {
        "res_id": str(res_id),
        "row": {
            "Risorsa:Consultant ID": str(res_id),
            "Nome Corso": "Kubernetes Fundamentals",
            "Stato": status,
        },
    }


def test_service_get__cache_hit__returns_cached_without_fetch() -> None:
    client = FakeRedis()
    cache = ReskillingCache(client=cast(redis.Redis, client), ttl_seconds=1800)
    cache.set(_record(100, ReskillingStatus.IN_PROGRESS))

    def _raise_client() -> ScraperClient:
        raise AssertionError("client factory should not be used on cache hit")

    service = ReskillingService(cache=cache, client_factory=_raise_client)

    result = service.get(100)

    assert result is not None
    assert result.res_id == 100
    assert result.status == ReskillingStatus.IN_PROGRESS


def test_service_get__cache_miss__fetches_and_caches() -> None:
    client = FakeRedis()
    cache = ReskillingCache(client=cast(redis.Redis, client), ttl_seconds=1800)
    calls: list[int] = []
    payloads = {200: _payload(200, "completed")}

    service = ReskillingService(
        cache=cache,
        client_factory=lambda: cast(ScraperClient, FakeScraperClient(payloads, calls)),
    )

    result = service.get(200)

    assert result is not None
    assert result.res_id == 200
    assert result.status == ReskillingStatus.COMPLETED
    assert calls == [200]
    assert cache.get(200) is not None


def test_service_get_bulk__fetches_missing_only() -> None:
    client = FakeRedis()
    cache = ReskillingCache(client=cast(redis.Redis, client), ttl_seconds=1800)
    cache.set(_record(100, ReskillingStatus.IN_PROGRESS))

    calls: list[int] = []
    payloads = {200: _payload(200, "planned")}

    service = ReskillingService(
        cache=cache,
        client_factory=lambda: cast(ScraperClient, FakeScraperClient(payloads, calls)),
    )

    result = service.get_bulk([100, 200])

    assert set(result.keys()) == {100, 200}
    assert result[100].status == ReskillingStatus.IN_PROGRESS
    assert result[200].status == ReskillingStatus.PLANNED
    assert calls == [200]


def test_service_filter__status__returns_only_matching_records() -> None:
    client = FakeRedis()
    cache = ReskillingCache(client=cast(redis.Redis, client), ttl_seconds=1800)
    calls: list[int] = []
    payloads = {
        100: _payload(100, "in progress"),
        200: _payload(200, "completed"),
    }

    service = ReskillingService(
        cache=cache,
        client_factory=lambda: cast(ScraperClient, FakeScraperClient(payloads, calls)),
    )

    result = service.filter([100, 200], status=ReskillingStatus.COMPLETED)

    assert list(result.keys()) == [200]
    assert result[200].status == ReskillingStatus.COMPLETED
