"""CSV loader for canonical availability format."""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import TextIO

from src.services.availability.cache import AvailabilityCache
from src.services.availability.schemas import AvailabilityStatus, ProfileAvailability

logger = logging.getLogger(__name__)


CANONICAL_HEADERS = (
    "res_id",
    "status",
    "allocation_pct",
    "current_project",
    "available_from",
    "updated_at",
)

ALLOCATION_PCT_MAX = 100


@dataclass(frozen=True)
class LoaderResult:
    """Summary of a CSV load operation."""

    total_rows: int
    loaded: int
    skipped: int


def load_from_csv(path: str | Path, cache: AvailabilityCache | None = None) -> LoaderResult:
    """Load availability data from a CSV file into Redis cache."""
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"Availability CSV not found: {resolved}")
    with resolved.open("r", encoding="utf-8", newline="") as handle:
        return load_from_stream(handle, cache=cache)


def load_from_stream(stream: TextIO, cache: AvailabilityCache | None = None) -> LoaderResult:
    """Load availability data from a CSV stream into Redis cache."""
    cache_instance = cache or AvailabilityCache()
    reader = csv.DictReader(stream)
    if not reader.fieldnames:
        raise ValueError("CSV header is required")

    missing = [name for name in CANONICAL_HEADERS if name not in reader.fieldnames]
    if missing:
        raise ValueError(f"Missing required CSV headers: {', '.join(missing)}")

    records: list[ProfileAvailability] = []
    total_rows = 0
    skipped = 0

    for row in reader:
        total_rows += 1
        record = _parse_row(row, row_number=total_rows)
        if record is None:
            skipped += 1
            continue
        records.append(record)

    if records:
        cache_instance.set_many(records)

    return LoaderResult(
        total_rows=total_rows,
        loaded=len(records),
        skipped=skipped,
    )


def _parse_row(row: dict[str, str | None], *, row_number: int) -> ProfileAvailability | None:
    res_id = _coerce_int(row.get("res_id"))
    if res_id is None:
        logger.warning("Skipping row %d: invalid res_id=%s", row_number, row.get("res_id"))
        return None

    status = _coerce_status(row.get("status"))
    if status is None:
        logger.warning("Skipping row %d: invalid status=%s", row_number, row.get("status"))
        return None

    allocation_pct = _coerce_int(row.get("allocation_pct"))
    if allocation_pct is None or allocation_pct < 0 or allocation_pct > ALLOCATION_PCT_MAX:
        logger.warning(
            "Skipping row %d: invalid allocation_pct=%s",
            row_number,
            row.get("allocation_pct"),
        )
        return None

    current_project = _clean_str(row.get("current_project"))
    available_from = _coerce_date(row.get("available_from"))
    updated_at = _coerce_datetime(row.get("updated_at"))
    if updated_at is None:
        logger.warning("Skipping row %d: invalid updated_at=%s", row_number, row.get("updated_at"))
        return None

    return ProfileAvailability(
        res_id=res_id,
        status=status,
        allocation_pct=allocation_pct,
        current_project=current_project,
        available_from=available_from,
        updated_at=updated_at,
    )


def _clean_str(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _coerce_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value.strip())
    except (ValueError, TypeError, AttributeError):
        return None


def _coerce_status(value: str | None) -> AvailabilityStatus | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    if not cleaned:
        return None
    try:
        return AvailabilityStatus(cleaned)
    except ValueError:
        return None


def _coerce_date(value: str | None) -> date | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        return date.fromisoformat(cleaned)
    except ValueError:
        return None


def _coerce_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if cleaned.endswith("Z"):
        cleaned = f"{cleaned[:-1]}+00:00"
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


__all__ = ["LoaderResult", "load_from_csv", "load_from_stream"]
