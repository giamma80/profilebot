"""Reskilling service with read-through cache behavior."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable

from src.services.reskilling.cache import ReskillingCache
from src.services.reskilling.normalizer import normalize_row_response
from src.services.reskilling.schemas import ReskillingRecord, ReskillingStatus
from src.services.scraper.client import ScraperClient

logger = logging.getLogger(__name__)


class ReskillingService:
    """Service orchestrating reskilling cache access and scraper fetches."""

    def __init__(
        self,
        cache: ReskillingCache | None = None,
        *,
        client_factory: Callable[[], ScraperClient] | None = None,
    ) -> None:
        self._cache = cache or ReskillingCache()
        self._client_factory = client_factory or ScraperClient

    @property
    def cache(self) -> ReskillingCache:
        """Return the reskilling cache instance."""
        return self._cache

    def get(self, res_id: int) -> ReskillingRecord | None:
        """Return reskilling data for a single res_id with read-through cache."""
        if not res_id:
            return None
        cached = self._cache.get(res_id)
        if cached is not None:
            return cached

        with self._client_factory() as client:
            return self._fetch_and_cache(res_id, client)

    def get_bulk(self, res_ids: Iterable[int]) -> dict[int, ReskillingRecord]:
        """Return reskilling data for multiple res_ids with read-through cache."""
        ids = [res_id for res_id in res_ids if res_id]
        if not ids:
            return {}

        cached = self._cache.get_many(ids)
        missing = [res_id for res_id in ids if res_id not in cached]
        if not missing:
            return cached

        with self._client_factory() as client:
            for res_id in missing:
                record = self._fetch_and_cache(res_id, client)
                if record is not None:
                    cached[res_id] = record

        return cached

    def filter(
        self,
        res_ids: Iterable[int],
        *,
        status: ReskillingStatus | str | None = None,
    ) -> dict[int, ReskillingRecord]:
        """Filter reskilling records by status."""
        records = self.get_bulk(res_ids)
        if status is None:
            return records

        normalized = self._normalize_status(status)
        if normalized is None:
            logger.warning("Unknown reskilling status filter '%s', returning unfiltered.", status)
            return records

        return {res_id: record for res_id, record in records.items() if record.status == normalized}

    def refresh(self, res_ids: Iterable[int]) -> dict[str, int]:
        """Refresh cache for the provided res_ids from the scraper service."""
        ids = [res_id for res_id in res_ids if res_id]
        if not ids:
            return {"total": 0, "loaded": 0, "skipped": 0}

        loaded = 0
        skipped = 0
        with self._client_factory() as client:
            for res_id in ids:
                record = self._fetch_and_cache(res_id, client)
                if record is None:
                    skipped += 1
                else:
                    loaded += 1

        return {"total": len(ids), "loaded": loaded, "skipped": skipped}

    def _fetch_and_cache(
        self,
        res_id: int,
        client: ScraperClient,
    ) -> ReskillingRecord | None:
        payload = client.fetch_reskilling_row(res_id)
        record = normalize_row_response(payload)
        if record is None:
            return None
        self._cache.set(record)
        return record

    def _normalize_status(
        self,
        status: ReskillingStatus | str,
    ) -> ReskillingStatus | None:
        if isinstance(status, ReskillingStatus):
            return status
        cleaned = status.strip().lower()
        if not cleaned:
            return None

        mapping = {
            "in_progress": ReskillingStatus.IN_PROGRESS,
            "in progress": ReskillingStatus.IN_PROGRESS,
            "ongoing": ReskillingStatus.IN_PROGRESS,
            "completed": ReskillingStatus.COMPLETED,
            "done": ReskillingStatus.COMPLETED,
            "finished": ReskillingStatus.COMPLETED,
            "planned": ReskillingStatus.PLANNED,
            "scheduled": ReskillingStatus.PLANNED,
        }
        if cleaned in mapping:
            return mapping[cleaned]

        try:
            return ReskillingStatus(cleaned)
        except ValueError:
            return None


__all__ = ["ReskillingService"]
