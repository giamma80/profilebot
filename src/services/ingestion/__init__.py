"""Ingestion abstraction layer — connector contract and adapters."""

from src.services.ingestion.contracts import IngestionSource
from src.services.ingestion.errors import (
    FetchError,
    IngestionError,
    NormalizationError,
    ValidationError,
)
from src.services.ingestion.profile_service import IngestionOutcome, ProfileIngestionService
from src.services.ingestion.schemas import IngestionMetadata, NormalizedDocument

__all__ = [
    "FetchError",
    "IngestionError",
    "IngestionMetadata",
    "IngestionOutcome",
    "IngestionSource",
    "NormalizationError",
    "NormalizedDocument",
    "ProfileIngestionService",
    "ValidationError",
]
