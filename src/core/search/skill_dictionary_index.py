"""Skill dictionary indexing utilities for semantic fallback."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable

from qdrant_client import QdrantClient, models

from src.core.embedding.service import EmbeddingService, OpenAIEmbeddingService
from src.core.skills.dictionary import SkillDictionary, SkillEntry
from src.services.qdrant.client import get_qdrant_client
from src.services.qdrant.collections import ensure_collections

logger = logging.getLogger(__name__)

_DEFAULT_BATCH_SIZE = 100


def index_skills_dictionary(
    dictionary: SkillDictionary,
    *,
    qdrant_client: QdrantClient | None = None,
    embedding_service: EmbeddingService | None = None,
    batch_size: int = _DEFAULT_BATCH_SIZE,
) -> int:
    """Index canonical skills into the skills_dictionary collection.

    Args:
        dictionary: Skill dictionary to index.
        qdrant_client: Optional Qdrant client instance.
        embedding_service: Optional embedding service for vector generation.
        batch_size: Number of skills to embed per batch.

    Returns:
        Number of indexed skill points.
    """
    client = qdrant_client or get_qdrant_client()
    ensure_collections(client)
    embedder = embedding_service or OpenAIEmbeddingService()

    canonical_items = list(dictionary.skills.items())
    if not canonical_items:
        logger.warning("No canonical skills found for indexing.")
        return 0

    total_indexed = 0
    for batch in _chunked(canonical_items, batch_size):
        names = [canonical for canonical, _ in batch]
        vectors = embedder.embed_batch(names)

        points: list[models.PointStruct] = []
        for (canonical, entry), vector in zip(batch, vectors, strict=False):
            point_id = _generate_skill_point_id(canonical)
            payload = {
                "canonical_name": canonical,
                "domain": entry.domain,
                "aliases_count": len(entry.aliases),
                "related_skills": entry.related,
            }
            points.append(models.PointStruct(id=point_id, vector=vector, payload=payload))

        if points:
            client.upsert(collection_name="skills_dictionary", points=points, wait=True)
            total_indexed += len(points)

    logger.info("Indexed %d skills into skills_dictionary", total_indexed)
    return total_indexed


def _chunked(
    items: list[tuple[str, SkillEntry]],
    batch_size: int,
) -> Iterable[list[tuple[str, SkillEntry]]]:
    if batch_size <= 0:
        return
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


def _generate_skill_point_id(canonical_name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"skills_dictionary:{canonical_name}"))
