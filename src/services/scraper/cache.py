"""Redis cache for scraper res IDs."""

from __future__ import annotations

import json

import redis

from src.core.config import get_settings

DEFAULT_RES_IDS_KEY = "profilebot:scraper:inside:res_ids"


class ScraperResIdCache:
    """Redis-backed cache for scraper res IDs."""

    def __init__(
        self,
        client: redis.Redis | None = None,
        *,
        key: str = DEFAULT_RES_IDS_KEY,
        ttl_seconds: int | None = None,
    ) -> None:
        settings = get_settings()
        self._client: redis.Redis = client or redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
        self._key = key
        self._ttl_seconds = ttl_seconds

    def get_res_ids(self) -> list[int]:
        """Return cached res IDs, or an empty list when missing."""
        raw = self._client.get(self._key)
        if not raw:
            return []
        payload = json.loads(raw)
        if not isinstance(payload, list):
            raise ValueError("Invalid res ID payload in cache")
        return [int(value) for value in payload]

    def set_res_ids(self, res_ids: list[int]) -> None:
        """Store res IDs in cache, optionally with TTL."""
        payload = json.dumps([int(value) for value in res_ids])
        if self._ttl_seconds:
            self._client.setex(self._key, self._ttl_seconds, payload)
        else:
            self._client.set(self._key, payload)

    def ping(self) -> bool:
        """Check Redis connectivity."""
        try:
            return bool(self._client.ping())
        except redis.RedisError:
            return False


__all__ = [
    "DEFAULT_RES_IDS_KEY",
    "ScraperResIdCache",
]
