"""String normalization helpers."""

from __future__ import annotations

from collections.abc import Iterable


def normalize_string_list(values: Iterable[object]) -> list[str]:
    """Normalize an iterable of values into a unique lowercase string list.

    Args:
        values: Iterable of raw values to normalize.

    Returns:
        Deduplicated, lowercase, stripped string list.
    """
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = str(value).strip().lower()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


__all__ = ["normalize_string_list"]
