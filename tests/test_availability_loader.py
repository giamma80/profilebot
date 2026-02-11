from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from io import StringIO
from pathlib import Path
from typing import cast

import pytest

from src.services.availability.cache import AvailabilityCache
from src.services.availability.loader import (
    LoaderResult,
    load_from_csv,
    load_from_stream,
)
from src.services.availability.schemas import AvailabilityStatus, ProfileAvailability


class FakeAvailabilityCache:
    def __init__(self) -> None:
        self.records: list[ProfileAvailability] = []

    def set_many(self, records: Iterable[ProfileAvailability]) -> None:
        self.records.extend(list(records))


def test_load_from_stream__valid_csv__loads_records() -> None:
    csv_data = (
        "res_id,status,allocation_pct,current_project,available_from,available_to,manager_name,updated_at\n"
        "100000,free,0,,,,,2026-02-10T08:00:00Z\n"
        "100001,partial,40,ProjectAlpha,,,Manager Uno,2026-02-10T08:00:00Z\n"
    )
    cache = FakeAvailabilityCache()

    result = load_from_stream(StringIO(csv_data), cache=cast(AvailabilityCache, cache))

    assert isinstance(result, LoaderResult)
    assert result.total_rows == 2
    assert result.loaded == 2
    assert result.skipped == 0
    assert len(cache.records) == 2
    assert cache.records[0].res_id == 100000
    assert cache.records[0].status == AvailabilityStatus.FREE
    assert cache.records[1].res_id == 100001
    assert cache.records[1].status == AvailabilityStatus.PARTIAL


def test_load_from_stream__missing_header__raises_value_error() -> None:
    csv_data = "res_id,status\n100000,free\n"
    with pytest.raises(ValueError, match="Missing required CSV headers"):
        load_from_stream(
            StringIO(csv_data),
            cache=cast(AvailabilityCache, FakeAvailabilityCache()),
        )


def test_load_from_stream__empty_header__raises_value_error() -> None:
    with pytest.raises(ValueError, match="CSV header is required"):
        load_from_stream(
            StringIO(""),
            cache=cast(AvailabilityCache, FakeAvailabilityCache()),
        )


def test_load_from_stream__invalid_rows__skipped_with_counts() -> None:
    csv_data = (
        "res_id,status,allocation_pct,current_project,available_from,available_to,manager_name,updated_at\n"
        "bad,free,0,,,,,2026-02-10T08:00:00Z\n"
        "100001,invalid,40,ProjectAlpha,,,Manager Uno,2026-02-10T08:00:00Z\n"
        "100002,busy,999,ProjectBeta,,2026-04-01,Manager Due,2026-02-10T08:00:00Z\n"
        "100003,free,0,,,,,not-a-date\n"
        "100004,free,0,,,,,2026-02-10T08:00:00Z\n"
    )
    cache = FakeAvailabilityCache()

    result = load_from_stream(StringIO(csv_data), cache=cast(AvailabilityCache, cache))

    assert result.total_rows == 5
    assert result.loaded == 1
    assert result.skipped == 4
    assert len(cache.records) == 1
    assert cache.records[0].res_id == 100004


def test_load_from_stream__optional_fields__parsed_correctly() -> None:
    csv_data = (
        "res_id,status,allocation_pct,current_project,available_from,available_to,manager_name,updated_at\n"
        "100010,free,0,,2026-03-01,2026-03-15,Manager Uno,2026-02-10T08:00:00Z\n"
    )
    cache = FakeAvailabilityCache()

    result = load_from_stream(StringIO(csv_data), cache=cast(AvailabilityCache, cache))

    assert result.loaded == 1
    record = cache.records[0]
    assert record.current_project is None
    assert record.available_from == date(2026, 3, 1)
    assert record.available_to == date(2026, 3, 15)
    assert record.manager_name == "Manager Uno"
    assert record.updated_at == datetime.fromisoformat("2026-02-10T08:00:00+00:00")


def test_load_from_csv__missing_file__raises_file_not_found(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.csv"
    with pytest.raises(FileNotFoundError, match="Availability CSV not found"):
        load_from_csv(
            missing_path,
            cache=cast(AvailabilityCache, FakeAvailabilityCache()),
        )
