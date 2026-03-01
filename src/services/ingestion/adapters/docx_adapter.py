"""DOCX CV ingestion adapter — wraps the existing DocxParser."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from src.core.parser.docx_parser import CVParseError, DocxParser
from src.core.parser.schemas import ParsedCV
from src.services.ingestion.errors import FetchError, NormalizationError, ValidationError
from src.services.ingestion.schemas import (
    ContentType,
    IngestionMetadata,
    NormalizedDocument,
    SourceType,
)

logger = logging.getLogger(__name__)


class DocxIngestionAdapter:
    """IngestionSource adapter for DOCX CV files.

    Wraps the existing ``DocxParser`` to conform to the ingestion contract.
    The ``identifier`` is the file path to the DOCX file.

    Backward-compatible: callers can still use ``DocxParser`` directly.
    This adapter adds the standardized fetch/validate/normalize lifecycle.
    """

    def __init__(self, parser: DocxParser | None = None) -> None:
        self._parser = parser or DocxParser()

    @property
    def source_type(self) -> str:
        return SourceType.DOCX_CV

    def fetch(self, identifier: str) -> bytes:
        """Read DOCX file from disk.

        Args:
            identifier: Path to the DOCX file.

        Returns:
            Raw bytes of the file.

        Raises:
            FetchError: If the file cannot be read.
        """
        path = Path(identifier)
        if not path.exists():
            raise FetchError(
                f"File not found: {path}",
                source_type=SourceType.DOCX_CV,
            )
        try:
            return path.read_bytes()
        except OSError as exc:
            raise FetchError(
                f"Failed to read file: {path}",
                source_type=SourceType.DOCX_CV,
            ) from exc

    def validate(self, raw: bytes) -> bool:
        """Validate DOCX content by checking the ZIP magic bytes and minimum size.

        Args:
            raw: Raw file bytes.

        Returns:
            True if the content looks like a valid DOCX.

        Raises:
            ValidationError: If the content is not a valid DOCX.
        """
        if len(raw) < 4:
            raise ValidationError(
                "Content too small to be a valid DOCX file",
                source_type=SourceType.DOCX_CV,
            )
        # DOCX files are ZIP archives — check magic bytes PK\x03\x04
        if raw[:4] != b"PK\x03\x04":
            raise ValidationError(
                "Content does not have DOCX/ZIP magic bytes",
                source_type=SourceType.DOCX_CV,
            )
        return True

    def normalize(self, identifier: str, raw: bytes) -> NormalizedDocument:
        """Parse DOCX and produce a NormalizedDocument.

        Args:
            identifier: Original file path (used for metadata).
            raw: Validated DOCX bytes.

        Returns:
            NormalizedDocument with parsed content and sections.

        Raises:
            NormalizationError: If parsing fails.
        """
        try:
            parsed = self._parse_from_bytes(raw, identifier)
        except CVParseError as exc:
            raise NormalizationError(
                f"DOCX parsing failed for {identifier}: {exc}",
                source_type=SourceType.DOCX_CV,
            ) from exc

        sections: dict[str, list[str]] = {}
        if parsed.skills:
            sections["skills"] = parsed.skills.skill_keywords
        if parsed.experiences:
            sections["experience"] = [exp.description for exp in parsed.experiences]
        if parsed.education:
            sections["education"] = parsed.education
        if parsed.certifications:
            sections["certifications"] = parsed.certifications

        metadata = IngestionMetadata(
            source_type=SourceType.DOCX_CV,
            content_type=ContentType.DOCX,
            source_identifier=str(identifier),
            extra={
                "cv_id": parsed.metadata.cv_id,
                "res_id": str(parsed.metadata.res_id),
                "full_name": parsed.metadata.full_name or "",
            },
        )

        return NormalizedDocument(
            metadata=metadata,
            content=parsed.raw_text,
            sections=sections,
        )

    def parse_legacy(self, file_path: str | Path) -> ParsedCV:
        """Backward-compatible direct parse (delegates to DocxParser).

        Use this when the caller still needs a ``ParsedCV`` object
        rather than a ``NormalizedDocument``.
        """
        return self._parser.parse(file_path)

    def _parse_from_bytes(self, raw: bytes, identifier: str) -> ParsedCV:
        """Parse DOCX from bytes using a temporary file."""
        suffix = Path(identifier).suffix or ".docx"
        name = Path(identifier).name
        with tempfile.NamedTemporaryFile(suffix=suffix, prefix=name + "_", delete=True) as tmp:
            tmp.write(raw)
            tmp.flush()
            return self._parser.parse(tmp.name)


__all__ = ["DocxIngestionAdapter"]
