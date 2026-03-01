"""Schemas for the ingestion abstraction layer."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SourceType(StrEnum):
    """Known ingestion source types."""

    DOCX_CV = "docx_cv"
    AVAILABILITY_CSV = "availability_csv"
    RESKILLING_API = "reskilling_api"


class ContentType(StrEnum):
    """Content types for ingested documents."""

    DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    JSON = "application/json"
    CSV = "text/csv"
    TEXT = "text/plain"


class IngestionMetadata(BaseModel):
    """Metadata attached to every ingested document."""

    source_type: SourceType
    schema_version: str = Field(default="1.0.0")
    content_type: ContentType
    source_identifier: str = Field(
        ..., description="Unique identifier within the source (e.g. res_id, filename)"
    )
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    extra: dict[str, str] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class NormalizedDocument(BaseModel):
    """Standard output of any IngestionSource after normalization."""

    metadata: IngestionMetadata
    content: str = Field(..., description="Normalized text content")
    sections: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Detected sections (e.g. skills, experience, education)",
    )
    raw_content: bytes | None = Field(default=None, description="Original raw bytes, if retained")

    model_config = {"extra": "forbid", "arbitrary_types_allowed": True}


__all__ = [
    "ContentType",
    "IngestionMetadata",
    "NormalizedDocument",
    "SourceType",
]
