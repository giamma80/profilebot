"""Availability service backed by cache-only API."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass

from src.services.availability.cache import AvailabilityCache
from src.services.availability.schemas import AvailabilityStatus, ProfileAvailability

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AvailabilityServiceConfig:
    """Configuration for availability service."""

    availability_mode_default: str = "any"


class AvailabilityService:
    """Service orchestrating availability cache access and filtering."""

    def __init__(
        self,
        cache: AvailabilityCache | None = None,
        *,
        config: AvailabilityServiceConfig | None = None,
    ) -> None:
        self._cache = cache or AvailabilityCache()
        self._config = config or AvailabilityServiceConfig()

    @property
    def cache(self) -> AvailabilityCache:
        return self._cache

    def get_availability(self, res_id: int) -> ProfileAvailability | None:
        """Return availability for a single res ID, using cache only."""
        return self._cache.get(res_id)

    def get(self, res_id: int) -> ProfileAvailability | None:
        """Alias for get_availability."""
        return self.get_availability(res_id)

    def get_availability_many(self, res_ids: Iterable[int]) -> dict[int, ProfileAvailability]:
        """Return availability records for res IDs, using cache only."""
        ids = [res_id for res_id in res_ids if res_id]
        if not ids:
            return {}
        return self._cache.get_many(ids)

    def get_bulk(self, res_ids: Iterable[int]) -> dict[int, ProfileAvailability]:
        """Alias for get_availability_many."""
        return self.get_availability_many(res_ids)

    def filter_res_ids(self, res_ids: Iterable[int], mode: str | None = None) -> list[int]:
        """Filter res IDs according to availability mode."""
        normalized_mode = (mode or self._config.availability_mode_default).strip().lower()
        ids = [res_id for res_id in res_ids if res_id]

        if normalized_mode == "any":
            return ids

        availability_data = self.get_availability_many(ids)
        if not availability_data:
            return []

        if normalized_mode == "only_free":
            return [
                res_id
                for res_id in ids
                if availability_data.get(res_id)
                and availability_data[res_id].status == AvailabilityStatus.FREE
            ]

        if normalized_mode == "free_or_partial":
            return [
                res_id
                for res_id in ids
                if availability_data.get(res_id)
                and availability_data[res_id].status
                in (AvailabilityStatus.FREE, AvailabilityStatus.PARTIAL)
            ]

        if normalized_mode == "unavailable":
            return [
                res_id
                for res_id in ids
                if availability_data.get(res_id)
                and availability_data[res_id].status == AvailabilityStatus.UNAVAILABLE
            ]

        logger.warning("Unknown availability mode '%s', returning unfiltered list.", mode)
        return ids


__all__ = [
    "AvailabilityService",
    "AvailabilityServiceConfig",
]
