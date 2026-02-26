from __future__ import annotations

import json
from typing import cast

import pytest
import redis

from src.services.scraper.cache import DEFAULT_RES_IDS_KEY, ScraperResIdCache


class FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._expirations: dict[str, int] = {}

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def set(self, key: str, value: str) -> None:
        self._store[key] = value

    def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value
        self._expirations[key] = ttl

    def ping(self) -> bool:
        return True


def test_cache_set_and_get_roundtrip() -> None:
    client = FakeRedis()
    cache = ScraperResIdCache(client=cast(redis.Redis, client))

    cache.set_res_ids([101, 202, 303])
    stored = cache.get_res_ids()

    assert stored == [101, 202, 303]


def test_cache_get_missing_returns_empty_list() -> None:
    cache = ScraperResIdCache(client=cast(redis.Redis, FakeRedis()))

    assert cache.get_res_ids() == []


def test_cache_set_res_ids_normalizes_values() -> None:
    client = FakeRedis()
    cache = ScraperResIdCache(client=cast(redis.Redis, client))

    cache.set_res_ids([101, 202, 303])
    raw = client.get(DEFAULT_RES_IDS_KEY)

    assert raw is not None
    assert json.loads(raw) == [101, 202, 303]


def test_cache_get_invalid_payload_raises_value_error() -> None:
    client = FakeRedis()
    client.set(DEFAULT_RES_IDS_KEY, json.dumps({"bad": "payload"}))
    cache = ScraperResIdCache(client=cast(redis.Redis, client))

    with pytest.raises(ValueError, match="Invalid res ID payload"):
        cache.get_res_ids()


def test_cache_set_res_ids_with_ttl_uses_setex() -> None:
    client = FakeRedis()
    cache = ScraperResIdCache(client=cast(redis.Redis, client), ttl_seconds=1800)

    cache.set_res_ids([101, 202])

    assert client._expirations[DEFAULT_RES_IDS_KEY] == 1800


def test_cache_ping_returns_true() -> None:
    cache = ScraperResIdCache(client=cast(redis.Redis, FakeRedis()))

    assert cache.ping() is True
