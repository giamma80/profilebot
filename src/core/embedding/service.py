"""Embedding service implementations."""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import cast

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


class EmbeddingService(ABC):
    """Abstract interface for embedding generation."""

    @property
    @abstractmethod
    def model(self) -> str:
        """Return the embedding model name."""
        raise NotImplementedError

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the embedding vector size."""
        raise NotImplementedError

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Generate an embedding for a single text input.

        Args:
            text: Input text to embed.

        Returns:
            Embedding vector.

        Raises:
            ValueError: If the input text is empty.
        """
        raise NotImplementedError

    @abstractmethod
    def embed_batch(self, texts: Iterable[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Args:
            texts: Iterable of input texts.

        Returns:
            List of embedding vectors aligned with input order.
        """
        raise NotImplementedError


class OpenAIEmbeddingService(EmbeddingService):
    """OpenAI embedding service with retry."""

    def __init__(self, client: OpenAI | None = None) -> None:
        """Initialize the embedding service.

        Args:
            client: Optional OpenAI client instance.
        """
        self._client = client or OpenAI()
        self._model = (
            _get_env("EMBEDDING_MODEL", "text-embedding-3-small") or "text-embedding-3-small"
        )
        dims_raw = _get_env("EMBEDDING_DIMENSIONS", "1536")
        self._dimensions = int(dims_raw) if dims_raw else 1536

    @property
    def model(self) -> str:
        """Return the configured embedding model name."""
        return self._model

    @property
    def dimensions(self) -> int:
        """Return the expected embedding vector size."""
        return self._dimensions

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def embed(self, text: str) -> list[float]:
        """Generate an embedding for a single text input.

        Args:
            text: Input text to embed.

        Returns:
            Embedding vector.

        Raises:
            ValueError: If the input text is empty.
        """
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("Text for embedding cannot be empty")

        logger.debug("Generating embedding with model '%s'", self._model)
        response = self._client.embeddings.create(model=self._model, input=cleaned)
        vector = cast(list[float], response.data[0].embedding)
        self._validate_dimensions(vector)
        return vector

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def embed_batch(self, texts: Iterable[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Args:
            texts: Iterable of input texts.

        Returns:
            List of embedding vectors aligned with input order.

        Raises:
            ValueError: If there are no valid texts to embed.
        """
        cleaned_texts = [text.strip() for text in texts if text and text.strip()]
        if not cleaned_texts:
            raise ValueError("No valid texts provided for embedding")

        logger.debug("Generating batch embeddings with model '%s'", self._model)
        response = self._client.embeddings.create(model=self._model, input=cleaned_texts)
        vectors = [cast(list[float], item.embedding) for item in response.data]
        for vector in vectors:
            self._validate_dimensions(vector)
        return vectors

    def _validate_dimensions(self, vector: list[float]) -> None:
        """Validate embedding vector size.

        Args:
            vector: Embedding vector to validate.
        """
        if len(vector) != self._dimensions:
            logger.warning(
                "Embedding dimension mismatch. Expected %d, got %d",
                self._dimensions,
                len(vector),
            )


__all__ = ["EmbeddingService", "OpenAIEmbeddingService"]
