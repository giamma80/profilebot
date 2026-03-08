"""Chunk-based search logic backed by Qdrant."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, cast

import redis
from qdrant_client import QdrantClient, models

from src.core.embedding.service import EmbeddingService, OpenAIEmbeddingService
from src.services.availability.cache import AvailabilityCache
from src.services.availability.schemas import AvailabilityStatus, ProfileAvailability
from src.services.qdrant.client import get_qdrant_client
from src.services.search.skill_search import ProfileMatch, SearchFilters

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChunkSearchResponse:
    """Search response payload for chunk search."""

    results: list[ProfileMatch]
    total: int
    limit: int
    offset: int
    query_time_ms: int


@dataclass(frozen=True)
class ChunkSearchDependencies:
    """Optional dependencies for chunk search."""

    qdrant_client: QdrantClient | None = None
    embedding_service: EmbeddingService | None = None


def search_by_chunks(
    query_text: str,
    *,
    filters: SearchFilters | None = None,
    limit: int = 10,
    offset: int = 0,
    dependencies: ChunkSearchDependencies | None = None,
) -> ChunkSearchResponse:
    """Search profiles by textual chunks using Qdrant vector search.

    Args:
        query_text: Raw text from the request (JD or skill query).
        filters: Optional filter constraints.
        limit: Maximum number of results to return.
        offset: Result offset for pagination.
        dependencies: Optional service dependencies overrides.

    Returns:
        Search response with ranked profile matches.
    """
    if not query_text.strip():
        return ChunkSearchResponse(results=[], total=0, limit=limit, offset=offset, query_time_ms=0)

    resolved = dependencies or ChunkSearchDependencies()
    start_time = time.perf_counter()
    embedder = resolved.embedding_service or OpenAIEmbeddingService()
    query_vector = embedder.embed(query_text)
    client = cast(Any, resolved.qdrant_client or get_qdrant_client())
    query_filter = _build_filter(filters)

    fetch_limit = max(0, limit) + max(0, offset)
    if hasattr(client, "search"):
        scored_points = client.search(
            collection_name="cv_chunks",
            query_vector=query_vector,
            query_filter=query_filter,
            limit=fetch_limit or 1,
            with_payload=True,
        )
    else:
        response = client.query_points(
            collection_name="cv_chunks",
            query=query_vector,
            query_filter=query_filter,
            limit=fetch_limit or 1,
            with_payload=True,
        )
        scored_points = response.points

    results = _build_matches(scored_points)
    paged = results[offset : offset + limit] if limit > 0 else []

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    return ChunkSearchResponse(
        results=paged,
        total=len(results),
        limit=limit,
        offset=offset,
        query_time_ms=elapsed_ms,
    )


def _build_filter(filters: SearchFilters | None) -> models.Filter | None:
    if not filters:
        return None

    conditions: list[models.FieldCondition] = []
    if filters.res_ids:
        conditions.append(
            models.FieldCondition(
                key="res_id",
                match=models.MatchAny(any=filters.res_ids),
            )
        )

    if filters.availability and filters.availability != "any":
        available_res_ids = _get_available_res_ids(filters.availability, filters.res_ids)
        if available_res_ids is None:
            logger.warning("Redis unreachable, falling back to availability='any'.")
        elif not available_res_ids:
            return _empty_filter()
        else:
            conditions.append(
                models.FieldCondition(
                    key="res_id",
                    match=models.MatchAny(any=available_res_ids),
                )
            )

    if not conditions:
        return None

    return models.Filter(must=cast(Any, conditions))


def _empty_filter() -> models.Filter:
    return models.Filter(
        must=[
            models.FieldCondition(
                key="res_id",
                match=models.MatchAny(any=[-1]),
            )
        ]
    )


def _get_available_res_ids(mode: str, res_ids: list[int] | None) -> list[int] | None:
    normalized = mode.strip().lower()
    try:
        cache = AvailabilityCache()
        if res_ids:
            records_by_id = cache.get_many(res_ids)
            return [
                res_id for res_id in res_ids if _matches_mode(records_by_id.get(res_id), normalized)
            ]
        records_list = cache.scan_records()
        return [record.res_id for record in records_list if _matches_mode(record, normalized)]
    except redis.RedisError:
        logger.warning("Redis unreachable, falling back to availability='any'.")
        return None


def _matches_mode(record: ProfileAvailability | None, mode: str) -> bool:
    if record is None:
        return False
    if mode == "only_free":
        return record.status == AvailabilityStatus.FREE
    if mode == "free_or_partial":
        return record.status in (AvailabilityStatus.FREE, AvailabilityStatus.PARTIAL)
    if mode == "unavailable":
        return record.status == AvailabilityStatus.UNAVAILABLE
    return False


def _build_matches(points: list[models.ScoredPoint]) -> list[ProfileMatch]:
    matches: list[ProfileMatch] = []

    for point in points:
        payload = point.payload if isinstance(point.payload, dict) else {}
        res_id = _extract_payload_int(payload, "res_id")
        cv_id = str(payload.get("cv_id", ""))

        if res_id <= 0 or not cv_id:
            logger.warning(
                "Skipping chunk result with missing identifiers: res_id=%s cv_id='%s'",
                res_id,
                cv_id,
            )
            continue

        matches.append(
            ProfileMatch(
                res_id=res_id,
                cv_id=cv_id,
                score=point.score or 0.0,
                matched_skills=[],
                missing_skills=[],
                skill_domain=None,
                seniority=None,
                payload=payload,
            )
        )

    matches.sort(key=lambda item: item.score, reverse=True)
    return matches


def _extract_payload_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
