"""Connector contract for ingestion sources."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.services.ingestion.schemas import NormalizedDocument


@runtime_checkable
class IngestionSource(Protocol):
    """Protocol that every ingestion connector must implement.

    Lifecycle:
        1. fetch()      — retrieve raw content + metadata
        2. validate()   — check format/schema of raw content
        3. normalize()  — produce a NormalizedDocument for the core layer

    Each method may raise the corresponding IngestionError subclass:
        - fetch()     → FetchError
        - validate()  → ValidationError
        - normalize() → NormalizationError
    """

    @property
    def source_type(self) -> str:
        """Return the source type identifier (e.g. 'docx_cv')."""
        ...

    def fetch(self, identifier: str) -> bytes:
        """Fetch raw content for the given identifier.

        Args:
            identifier: Source-specific identifier (file path, URL, res_id, etc.).

        Returns:
            Raw bytes of the fetched content.

        Raises:
            FetchError: If fetching fails.
        """
        ...

    def validate(self, raw: bytes) -> bool:
        """Validate raw content format and integrity.

        Args:
            raw: Raw bytes to validate.

        Returns:
            True if valid.

        Raises:
            ValidationError: If validation fails.
        """
        ...

    def normalize(self, identifier: str, raw: bytes) -> NormalizedDocument:
        """Normalize raw content into a NormalizedDocument.

        Args:
            identifier: Source-specific identifier (for metadata).
            raw: Validated raw bytes.

        Returns:
            A NormalizedDocument ready for the core layer.

        Raises:
            NormalizationError: If normalization fails.
        """
        ...


__all__ = ["IngestionSource"]
