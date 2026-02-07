"""Pydantic schemas for embedding results."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EmbeddingResult(BaseModel):
    """Embedding result for a single text input.

    Args:
        text: Original text used to generate the embedding.
        vector: Embedding vector.
        model: Embedding model name.
        dimensions: Expected embedding vector size.
    """

    text: str
    vector: list[float]
    model: str
    dimensions: int = Field(..., ge=1)


class BatchEmbeddingResult(BaseModel):
    """Embedding result for a batch of texts.

    Args:
        items: Embedding results for successfully processed texts.
        failed_texts: Texts that failed to embed.
        model: Embedding model name.
        dimensions: Expected embedding vector size.
    """

    items: list[EmbeddingResult] = Field(default_factory=list)
    failed_texts: list[str] = Field(default_factory=list)
    model: str
    dimensions: int = Field(..., ge=1)

    @property
    def total(self) -> int:
        """Return total number of inputs (success + failed)."""
        return len(self.items) + len(self.failed_texts)


__all__ = ["BatchEmbeddingResult", "EmbeddingResult"]
