"""Redis cache layer for availability records."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import cast

import redis

from src.core.config import get_settings
from src.services.availability.schemas import ProfileAvailability


class AvailabilityCache:
    """Redis-backed cache for availability records."""

    def __init__(
        self,
        client: redis.Redis | None = None,
        *,
        ttl_seconds: int | None = None,
        key_prefix: str = "profilebot:availability",
    ) -> None:
        settings = get_settings()
        self._client: redis.Redis = client or redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
        self._ttl_seconds = ttl_seconds or settings.availability_cache_ttl
        self._key_prefix = key_prefix.strip(":") or "profilebot:availability"

    def _make_key(self, res_id: int) -> str:
        return f"{self._key_prefix}:{res_id}"

    def get(self, res_id: int) -> ProfileAvailability | None:
        """Return a cached availability record, if present."""
        if not res_id:
            return None
        raw = cast(str | None, self._client.get(self._make_key(res_id)))
        if not raw:
            return None
        return cast(ProfileAvailability, ProfileAvailability.model_validate_json(raw))

    def get_many(self, res_ids: Iterable[int]) -> dict[int, ProfileAvailability]:
        """Return cached records for the requested res IDs."""
        ids = [res_id for res_id in res_ids if res_id]
        if not ids:
            return {}
        keys = [self._make_key(res_id) for res_id in ids]
        raw_values = cast(list[str | None], self._client.mget(keys))
        results: dict[int, ProfileAvailability] = {}
        for res_id, raw in zip(ids, raw_values, strict=False):
            if not raw:
                continue
            results[res_id] = cast(
                ProfileAvailability, ProfileAvailability.model_validate_json(raw)
            )
        return results

    def scan_records(self, *, batch_size: int = 500) -> list[ProfileAvailability]:
        """Scan all availability records in the cache."""
        pattern = f"{self._key_prefix}:*"
        records: list[ProfileAvailability] = []
        cursor = 0
        while True:
            cursor, keys = cast(
                tuple[int, list[str]],
                self._client.scan(cursor=cursor, match=pattern, count=batch_size),
            )
            if keys:
                raw_values = cast(list[str | None], self._client.mget(keys))
                for raw in raw_values:
                    if not raw:
                        continue
                    try:
                        records.append(
                            cast(ProfileAvailability, ProfileAvailability.model_validate_json(raw))
                        )
                    except Exception:  # pragma: no cover
                        continue
            if cursor == 0:
                break
        return records

    def set(self, availability: ProfileAvailability) -> None:
        """Store a single availability record in cache."""
        key = self._make_key(availability.res_id)
        payload = availability.model_dump_json()
        self._client.setex(key, self._ttl_seconds, payload)

    def set_many(self, records: Iterable[ProfileAvailability]) -> None:
        """Store multiple availability records in cache with TTL."""
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

    def touch(self, res_id: int, updated_at: datetime | None = None) -> None:
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
