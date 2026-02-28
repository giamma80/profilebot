"""Redis cache layer for reskilling records."""

from __future__ import annotations

from collections.abc import Iterable
from typing import cast

import redis

from src.core.config import get_settings
from src.services.reskilling.schemas import ReskillingRecord


class ReskillingCache:
    """Redis-backed cache for reskilling records."""

    def __init__(
        self,
        client: redis.Redis | None = None,
        *,
        ttl_seconds: int | None = None,
        key_prefix: str = "profilebot:reskilling",
    ) -> None:
        settings = get_settings()
        self._client: redis.Redis = client or redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
        self._ttl_seconds = ttl_seconds or settings.reskilling_cache_ttl
        self._key_prefix = key_prefix.strip(":") or "profilebot:reskilling"

    def _make_key(self, res_id: int) -> str:
        return f"{self._key_prefix}:{res_id}"

    def get(self, res_id: int) -> ReskillingRecord | None:
        """Return a cached reskilling record, if present."""
        if not res_id:
            return None
        raw = cast(str | None, self._client.get(self._make_key(res_id)))
        if not raw:
            return None
        return cast(ReskillingRecord, ReskillingRecord.model_validate_json(raw))

    def get_many(self, res_ids: Iterable[int]) -> dict[int, ReskillingRecord]:
        """Return cached records for the requested res IDs."""
        ids = [res_id for res_id in res_ids if res_id]
        if not ids:
            return {}
        keys = [self._make_key(res_id) for res_id in ids]
        raw_values = cast(list[str | None], self._client.mget(keys))
        results: dict[int, ReskillingRecord] = {}
        for res_id, raw in zip(ids, raw_values, strict=False):
            if not raw:
                continue
            results[res_id] = cast(ReskillingRecord, ReskillingRecord.model_validate_json(raw))
        return results

    def set(self, record: ReskillingRecord) -> None:
        """Store a single reskilling record in cache."""
        key = self._make_key(record.res_id)
        payload = record.model_dump_json()
        self._client.setex(key, self._ttl_seconds, payload)

    def set_many(self, records: Iterable[ReskillingRecord]) -> None:
        """Store multiple reskilling records in cache with TTL."""
        payloads: dict[str, str] = {}
        for record in records:
            if not record.res_id:
                continue
            payloads[self._make_key(record.res_id)] = record.model_dump_json()

        if not payloads:
            return

        for key, payload in payloads.items():
            self._client.setex(key, self._ttl_seconds, payload)

    def invalidate(self, res_id: int) -> None:
        """Remove a single cache entry."""
        if not res_id:
            return
        self._client.delete(self._make_key(res_id))

    def touch(self, res_id: int) -> None:
        """Refresh TTL for an entry if it exists."""
        if not res_id:
            return
        key = self._make_key(res_id)
        if self._client.exists(key):
            self._client.expire(key, self._ttl_seconds)

    def ping(self) -> bool:
        """Check Redis connectivity."""
        try:
            return bool(self._client.ping())
        except redis.RedisError:
            return False


__all__ = ["ReskillingCache"]
