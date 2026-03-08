"""Semantic fallback helpers for skills dictionary recovery."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from qdrant_client import QdrantClient

from src.core.embedding.service import EmbeddingService, OpenAIEmbeddingService
from src.services.qdrant.client import get_qdrant_client

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FallbackOptions:
    """Options for semantic fallback lookup."""

    top_k: int = 5
    score_threshold: float = 0.7
    domain_filter: str | None = None


@dataclass(frozen=True)
class FallbackDependencies:
    """Dependencies for semantic fallback lookup."""

    qdrant_client: QdrantClient | None = None
    embedding_service: EmbeddingService | None = None


def recover_skills_from_dictionary(
    query_text: str,
    *,
    options: FallbackOptions | None = None,
    dependencies: FallbackDependencies | None = None,
) -> list[str]:
    """Recover canonical skills from the skills_dictionary collection.

    Args:
        query_text: Text used to query the skills dictionary.
        options: Optional fallback options (thresholds, top_k, domain filter).
        dependencies: Optional dependency overrides for Qdrant and embeddings.

    Returns:
        List of canonical skills recovered from the dictionary.
    """
    if not query_text.strip():
        return []

    resolved_options = options or FallbackOptions()
    resolved_dependencies = dependencies or FallbackDependencies()
    top_k = resolved_options.top_k
    score_threshold = resolved_options.score_threshold
    domain_filter = resolved_options.domain_filter

    client = resolved_dependencies.qdrant_client or get_qdrant_client()
    embedder = resolved_dependencies.embedding_service or OpenAIEmbeddingService()
    query_vector = embedder.embed(query_text)

    if hasattr(client, "search"):
        points = client.search(
            collection_name="skills_dictionary",
            query_vector=query_vector,
            limit=max(1, top_k),
            with_payload=True,
        )
    else:
        response = client.query_points(
            collection_name="skills_dictionary",
            query=query_vector,
            limit=max(1, top_k),
            with_payload=True,
        )
        points = response.points

    recovered: list[str] = []
    seen: set[str] = set()

    for point in points:
        score = point.score or 0.0
        if score < score_threshold:
            continue
        payload = point.payload if isinstance(point.payload, dict) else {}
        canonical_name = payload.get("canonical_name")
        if not isinstance(canonical_name, str):
            continue
        canonical = canonical_name.strip().lower()
        if not canonical or canonical in seen:
            continue
        if domain_filter:
            payload_domain = payload.get("domain")
            if isinstance(payload_domain, str) and payload_domain.strip().lower() != domain_filter:
                continue
        seen.add(canonical)
        recovered.append(canonical)

    if not recovered:
        logger.info(
            "No skills recovered from skills_dictionary (threshold=%s, domain=%s)",
            score_threshold,
            domain_filter,
        )
    return recovered
