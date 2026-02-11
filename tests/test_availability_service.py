from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import cast

from src.services.availability.cache import AvailabilityCache
from src.services.availability.schemas import AvailabilityStatus, ProfileAvailability
from src.services.availability.service import AvailabilityService


class FakeAvailabilityCache:
    def __init__(self, records: dict[int, ProfileAvailability]) -> None:
        self._records = records

    def get_many(self, res_ids: Iterable[int]) -> dict[int, ProfileAvailability]:
        return {res_id: self._records[res_id] for res_id in res_ids if res_id in self._records}

    def get(self, res_id: int) -> ProfileAvailability | None:
        return self._records.get(res_id)


def _record(res_id: int, status: AvailabilityStatus, allocation_pct: int) -> ProfileAvailability:
    return ProfileAvailability(
        res_id=res_id,
        status=status,
        allocation_pct=allocation_pct,
        current_project=None,
        available_from=None,
        updated_at=datetime(2026, 2, 10, 8, 0, 0, tzinfo=UTC),
    )


def test_filter_res_ids__any_returns_all_ids() -> None:
    cache = FakeAvailabilityCache(
        {
            100: _record(100, AvailabilityStatus.FREE, 0),
            200: _record(200, AvailabilityStatus.BUSY, 100),
        }
    )
    service = AvailabilityService(cache=cast(AvailabilityCache, cache))

    result = service.filter_res_ids([100, 200], mode="any")

    assert result == [100, 200]


def test_filter_res_ids__only_free_returns_free_only() -> None:
    cache = FakeAvailabilityCache(
        {
            100: _record(100, AvailabilityStatus.FREE, 0),
            200: _record(200, AvailabilityStatus.PARTIAL, 40),
            300: _record(300, AvailabilityStatus.BUSY, 100),
        }
    )
    service = AvailabilityService(cache=cast(AvailabilityCache, cache))

    result = service.filter_res_ids([100, 200, 300], mode="only_free")

    assert result == [100]


def test_filter_res_ids__free_or_partial_returns_free_and_partial() -> None:
    cache = FakeAvailabilityCache(
        {
            100: _record(100, AvailabilityStatus.FREE, 0),
            200: _record(200, AvailabilityStatus.PARTIAL, 40),
            300: _record(300, AvailabilityStatus.BUSY, 100),
        }
    )
    service = AvailabilityService(cache=cast(AvailabilityCache, cache))

    result = service.filter_res_ids([100, 200, 300], mode="free_or_partial")

    assert result == [100, 200]


def test_filter_res_ids__unavailable_returns_only_unavailable() -> None:
    cache = FakeAvailabilityCache(
        {
            100: _record(100, AvailabilityStatus.UNAVAILABLE, 0),
            200: _record(200, AvailabilityStatus.BUSY, 100),
        }
    )
    service = AvailabilityService(cache=cast(AvailabilityCache, cache))

    result = service.filter_res_ids([100, 200], mode="unavailable")

    assert result == [100]


def test_filter_res_ids__missing_records_are_excluded() -> None:
    cache = FakeAvailabilityCache(
        {
            100: _record(100, AvailabilityStatus.FREE, 0),
        }
    )
    service = AvailabilityService(cache=cast(AvailabilityCache, cache))

    result = service.filter_res_ids([100, 999], mode="only_free")

    assert result == [100]


def test_filter_res_ids__no_cache_entries_returns_empty() -> None:
    cache = FakeAvailabilityCache({})
    service = AvailabilityService(cache=cast(AvailabilityCache, cache))

    result = service.filter_res_ids([100, 200], mode="only_free")

    assert result == []
