"""Skill-based search logic backed by Qdrant."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from qdrant_client import QdrantClient, models

from src.core.embedding.service import EmbeddingService, OpenAIEmbeddingService
from src.core.skills.dictionary import SkillDictionary, load_skill_dictionary
from src.core.skills.normalizer import SkillNormalizer
from src.services.qdrant.client import get_qdrant_client
from src.services.search.scoring import calculate_final_score

logger = logging.getLogger(__name__)

DEFAULT_DICTIONARY_PATH = "data/skills_dictionary.yaml"


@dataclass(frozen=True)
class SearchFilters:
    """Optional filters for skill-based search."""

    res_ids: list[int] | None = None
    skill_domains: list[str] | None = None
    seniority: list[str] | None = None
    availability: str | None = None


@dataclass(frozen=True)
class ProfileMatch:
    """Single profile match result."""

    res_id: int
    cv_id: str
    score: float
    matched_skills: list[str]
    missing_skills: list[str]
    skill_domain: str | None = None
    seniority: str | None = None


@dataclass(frozen=True)
class SkillSearchResponse:
    """Search response payload."""

    results: list[ProfileMatch]
    total: int
    limit: int
    offset: int
    query_time_ms: int


def search_by_skills(
    skills: list[str],
    *,
    filters: SearchFilters | None = None,
    limit: int = 10,
    offset: int = 0,
    qdrant_client: QdrantClient | None = None,
    embedding_service: EmbeddingService | None = None,
    dictionary: SkillDictionary | None = None,
) -> SkillSearchResponse:
    """Search profiles by skills using Qdrant vector search.

    Args:
        skills: Raw skill strings from the request.
        filters: Optional filter constraints.
        limit: Maximum number of results to return.
        offset: Result offset for pagination.
        qdrant_client: Optional Qdrant client instance.
        embedding_service: Optional embedding service instance.
        dictionary: Optional skill dictionary override.

    Returns:
        Search response with ranked profile matches.

    Raises:
        ValueError: If no skills are provided after normalization.
    """
    start_time = time.perf_counter()
    normalized_skills = _normalize_query_skills(skills, dictionary)
    if not normalized_skills:
        raise ValueError("At least one valid skill is required")

    query_vector = (embedding_service or OpenAIEmbeddingService()).embed(
        ", ".join(normalized_skills)
    )
    client = cast(Any, qdrant_client or get_qdrant_client())
    query_filter = _build_filter(filters)

    fetch_limit = max(0, limit) + max(0, offset)
    scored_points = client.search(
        collection_name="cv_skills",
        query_vector=query_vector,
        query_filter=query_filter,
        limit=fetch_limit or 1,
        with_payload=True,
    )

    results = _build_matches(scored_points, normalized_skills)
    paged = results[offset : offset + limit] if limit > 0 else []

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    return SkillSearchResponse(
        results=paged,
        total=len(results),
        limit=limit,
        offset=offset,
        query_time_ms=elapsed_ms,
    )


def _normalize_query_skills(
    skills: list[str],
    dictionary: SkillDictionary | None,
) -> list[str]:
    dictionary_instance = dictionary or load_skill_dictionary(_resolve_dictionary_path())
    normalizer = SkillNormalizer(dictionary_instance)

    normalized: list[str] = []
    seen: set[str] = set()
    for skill in skills:
        if not skill:
            continue
        normalized_skill = normalizer.normalize(skill)
        if normalized_skill is None:
            continue
        canonical = normalized_skill.canonical.strip().lower()
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        normalized.append(canonical)
    return normalized


def _resolve_dictionary_path() -> Path:
    env_path = os.getenv("SKILLS_DICTIONARY_PATH")
    return Path(env_path or DEFAULT_DICTIONARY_PATH)


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
    if filters.skill_domains:
        conditions.append(
            models.FieldCondition(
                key="skill_domain",
                match=models.MatchAny(any=_normalize_list(filters.skill_domains)),
            )
        )
    if filters.seniority:
        conditions.append(
            models.FieldCondition(
                key="seniority_bucket",
                match=models.MatchAny(any=_normalize_list(filters.seniority)),
            )
        )

    if filters.availability and filters.availability != "any":
        # TODO(US-007): apply availability filter when availability service is available.
        logger.warning(
            "Availability filter requested but not implemented, ignoring value '%s'",
            filters.availability,
        )

    if not conditions:
        return None

    return models.Filter(must=cast(Any, conditions))


def _build_matches(
    points: list[models.ScoredPoint],
    normalized_query: list[str],
) -> list[ProfileMatch]:
    query_set = set(normalized_query)
    matches: list[ProfileMatch] = []

    for point in points:
        payload = point.payload or {}
        normalized_skills = _extract_payload_list(payload, "normalized_skills")
        matched = query_set.intersection(normalized_skills)
        missing = query_set.difference(matched)
        res_id = _extract_payload_int(payload, "res_id")
        cv_id = str(payload.get("cv_id", ""))

        if res_id <= 0 or not cv_id:
            logger.warning(
                "Skipping search result with missing identifiers: res_id=%s cv_id='%s'",
                res_id,
                cv_id,
            )
            continue

        final_score = calculate_final_score(
            similarity=point.score or 0.0,
            matched=matched,
            query=query_set,
        )

        ordered_matched = [skill for skill in normalized_query if skill in matched]
        ordered_missing = [skill for skill in normalized_query if skill in missing]

        matches.append(
            ProfileMatch(
                res_id=res_id,
                cv_id=cv_id,
                score=final_score,
                matched_skills=ordered_matched,
                missing_skills=ordered_missing,
                skill_domain=_extract_payload_str(payload, "skill_domain"),
                seniority=_extract_payload_str(payload, "seniority_bucket"),
            )
        )

    matches.sort(
        key=lambda item: (item.score, len(item.matched_skills)),
        reverse=True,
    )
    return matches


def _extract_payload_list(payload: dict[str, Any], key: str) -> set[str]:
    raw = payload.get(key, [])
    if isinstance(raw, list):
        return {str(item).strip().lower() for item in raw if str(item).strip()}
    return set()


def _extract_payload_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _extract_payload_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _normalize_list(values: list[str]) -> list[str]:
    return [str(value).strip().lower() for value in values if str(value).strip()]
