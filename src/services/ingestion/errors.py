"""Error hierarchy for the ingestion layer."""

from __future__ import annotations


class IngestionError(Exception):
    """Base error for all ingestion failures."""

    def __init__(self, message: str, *, source_type: str | None = None) -> None:
        self.source_type = source_type
        super().__init__(message)


class FetchError(IngestionError):
    """Raised when fetching raw content fails (network, file I/O, etc.)."""


class ValidationError(IngestionError):
    """Raised when raw content fails schema or format validation."""


class NormalizationError(IngestionError):
    """Raised when normalization of validated content fails."""


__all__ = [
    "FetchError",
    "IngestionError",
    "NormalizationError",
    "ValidationError",
]
