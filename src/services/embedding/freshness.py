"""Redis-backed freshness gate for res_id ingestion."""

from __future__ import annotations

import redis

from src.core.config import get_settings

DEFAULT_FRESHNESS_PREFIX = "profilebot:freshness"


class FreshnessGate:
    """Gate ingestion for res_ids using Redis TTL keys."""

    def __init__(
        self,
        client: redis.Redis | None = None,
        *,
        ttl_seconds: int | None = None,
        key_prefix: str = DEFAULT_FRESHNESS_PREFIX,
    ) -> None:
        settings = get_settings()
        self._client: redis.Redis = client or redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
        self._ttl_seconds = ttl_seconds or settings.freshness_ttl_seconds
        self._key_prefix = key_prefix.strip(":") or DEFAULT_FRESHNESS_PREFIX

    def _make_key(self, res_id: int) -> str:
        return f"{self._key_prefix}:{res_id}"

    def is_fresh(self, res_id: int) -> bool:
        """Return True when res_id is still within freshness TTL.

        Args:
            res_id: Resource identifier.

        Returns:
            True if the freshness key exists.
        """
        if not res_id:
            return False
        return bool(self._client.exists(self._make_key(res_id)))

    def acquire(self, res_id: int) -> bool:
        """Set freshness TTL if not already present.

        Args:
            res_id: Resource identifier.

        Returns:
            True when the key was set, False when already present.
        """
        if not res_id:
            return False
        return bool(
            self._client.set(
                self._make_key(res_id),
                "1",
                ex=self._ttl_seconds,
                nx=True,
            )
        )

    def release(self, res_id: int) -> None:
        """Remove freshness key, allowing future ingestion.

        Args:
            res_id: Resource identifier.
        """
        if not res_id:
            return
        self._client.delete(self._make_key(res_id))


__all__ = [
    "DEFAULT_FRESHNESS_PREFIX",
    "FreshnessGate",
]
