"""Skill-based search logic backed by Qdrant."""

from __future__ import annotations

import logging
import os
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import redis
from qdrant_client import QdrantClient, models

from src.core.config import get_settings
from src.core.embedding.service import EmbeddingService, OpenAIEmbeddingService
from src.core.search.fallback import FallbackOptions, recover_skills_from_dictionary
from src.core.skills.dictionary import SkillDictionary, load_skill_dictionary
from src.core.skills.normalizer import SkillNormalizer
from src.services.availability.cache import AvailabilityCache
from src.services.availability.schemas import AvailabilityStatus, ProfileAvailability
from src.services.qdrant.client import get_qdrant_client
from src.services.search.metrics import FALLBACK_ACTIVATED
from src.services.search.scoring import (
    calculate_final_score,
    calculate_weighted_final_score,
    calculate_weighted_match_ratio,
)
from src.utils.normalization import normalize_string_list

logger = logging.getLogger(__name__)

DEFAULT_DICTIONARY_PATH = "data/skills_dictionary.yaml"

_SENIORITY_RANK = {"junior": 0, "mid": 1, "senior": 2, "lead": 3}


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
    payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class SkillSearchResponse:
    """Search response payload."""

    results: list[ProfileMatch]
    total: int
    limit: int
    offset: int
    query_time_ms: int
    candidates_by_skills: list[ProfileMatch] | None = None
    candidates_by_chunks: list[ProfileMatch] | None = None
    candidates_fused: list[ProfileMatch] | None = None
    fallback_activated: bool = False
    recovered_skills: list[str] | None = None
    no_match_reason: str | None = None
    fusion_strategy: str | None = None
    search_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class SearchDependencies:
    """Optional dependencies for skill search."""

    qdrant_client: QdrantClient | None = None
    embedding_service: EmbeddingService | None = None
    dictionary: SkillDictionary | None = None


def search_by_skills(
    skills: list[str],
    *,
    filters: SearchFilters | None = None,
    limit: int = 10,
    offset: int = 0,
    dependencies: SearchDependencies | None = None,
) -> SkillSearchResponse:
    """Search profiles by skills using Qdrant vector search.

    Args:
        skills: Raw skill strings from the request.
        filters: Optional filter constraints.
        limit: Maximum number of results to return.
        offset: Result offset for pagination.
        dependencies: Optional service dependencies overrides.

    Returns:
        Search response with ranked profile matches.

    Raises:
        ValueError: If no skills are provided after normalization.
    """
    resolved = dependencies or SearchDependencies()
    start_time = time.perf_counter()
    settings = get_settings()
    fallback_activated = False
    recovered_skills: list[str] | None = None
    dictionary_instance = resolved.dictionary or load_skill_dictionary(_resolve_dictionary_path())
    normalized_skills = _normalize_query_skills(skills, dictionary_instance)
    if not normalized_skills:
        if settings.search_fallback_enabled:
            recovered = recover_skills_from_dictionary(
                query_text=" ".join(skills),
                options=FallbackOptions(top_k=5, score_threshold=0.7),
            )
            fallback_activated = True
            FALLBACK_ACTIVATED.inc()
            if recovered:
                recovered_skills = recovered
                normalized_skills = recovered
                logger.info(
                    "FALLBACK_SKILL_RECOVERY via skills_dictionary: recovered %s",
                    recovered,
                )
            else:
                logger.info("FALLBACK_SKILL_RECOVERY: no skills recovered (threshold=0.7)")
                elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                return SkillSearchResponse(
                    results=[],
                    total=0,
                    limit=limit,
                    offset=offset,
                    query_time_ms=elapsed_ms,
                    candidates_by_skills=[],
                    candidates_by_chunks=None,
                    candidates_fused=None,
                    fallback_activated=True,
                    recovered_skills=None,
                    no_match_reason="no_normalizable_skills_even_with_semantic_fallback",
                    fusion_strategy=None,
                    search_metadata=None,
                )
        else:
            raise ValueError("At least one valid skill is required")

    query_domain = _resolve_query_domain(normalized_skills, dictionary_instance)
    query_seniority = (
        filters.seniority[0].strip().lower() if filters and filters.seniority else None
    )

    query_vector = (resolved.embedding_service or OpenAIEmbeddingService()).embed(
        ", ".join(normalized_skills)
    )
    client = cast(Any, resolved.qdrant_client or get_qdrant_client())
    query_filter = _build_filter(filters)

    fetch_limit = max(0, limit) + max(0, offset)
    if hasattr(client, "search"):
        scored_points = client.search(
            collection_name="cv_skills",
            query_vector=query_vector,
            query_filter=query_filter,
            limit=fetch_limit or 1,
            with_payload=True,
        )
    else:
        response = client.query_points(
            collection_name="cv_skills",
            query=query_vector,
            query_filter=query_filter,
            limit=fetch_limit or 1,
            with_payload=True,
        )
        scored_points = response.points

    results = _build_matches(scored_points, normalized_skills, query_domain, query_seniority)
    paged = results[offset : offset + limit] if limit > 0 else []

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    return SkillSearchResponse(
        results=paged,
        total=len(results),
        limit=limit,
        offset=offset,
        query_time_ms=elapsed_ms,
        candidates_by_skills=paged,
        candidates_by_chunks=None,
        candidates_fused=None,
        fallback_activated=fallback_activated,
        recovered_skills=recovered_skills,
        no_match_reason=None,
        fusion_strategy=None,
        search_metadata=None,
    )


def _normalize_query_skills(
    skills: list[str],
    dictionary: SkillDictionary,
) -> list[str]:
    normalizer = SkillNormalizer(dictionary)

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


def _resolve_query_domain(
    normalized_skills: list[str],
    dictionary: SkillDictionary,
) -> str | None:
    domains: list[str] = []
    for skill in normalized_skills:
        entry = dictionary.get_by_canonical(skill)
        if entry and entry.domain:
            domains.append(entry.domain)
    if not domains:
        return None
    return Counter(domains).most_common(1)[0][0]


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


def _build_matches(
    points: list[models.ScoredPoint],
    normalized_query: list[str],
    query_domain: str | None,
    query_seniority: str | None,
) -> list[ProfileMatch]:
    query_set = set(normalized_query)
    matches: list[ProfileMatch] = []
    settings = get_settings()

    for point in points:
        payload = point.payload if isinstance(point.payload, dict) else {}
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

        if settings.scoring_use_weighted:
            weight_map = _extract_weight_map(payload)
            weighted_match_ratio = calculate_weighted_match_ratio(
                matched,
                normalized_query,
                weight_map,
            )
            payload_domain = _extract_payload_str(payload, "skill_domain")
            payload_seniority = _extract_payload_str(payload, "seniority") or _extract_payload_str(
                payload, "seniority_bucket"
            )
            domain_boost = _calculate_domain_boost(query_domain, payload_domain)
            seniority_penalty = _calculate_seniority_penalty(query_seniority, payload_seniority)
            final_score = calculate_weighted_final_score(
                similarity=point.score or 0.0,
                weighted_match_ratio=weighted_match_ratio,
                domain_boost=domain_boost,
                seniority_penalty=seniority_penalty,
            )
        else:
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
                payload=payload,
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


def _calculate_domain_boost(query_domain: str | None, profile_domain: str | None) -> float:
    if not query_domain or not profile_domain:
        return 0.0
    return 1.2 if query_domain == profile_domain else 0.0


def _calculate_seniority_penalty(
    query_seniority: str | None,
    profile_seniority: str | None,
) -> float:
    if not query_seniority or not profile_seniority:
        return 0.0
    query_rank = _SENIORITY_RANK.get(query_seniority)
    profile_rank = _SENIORITY_RANK.get(profile_seniority)
    if query_rank is None or profile_rank is None:
        return 0.0
    return abs(query_rank - profile_rank) * 0.05


def _extract_weight_map(payload: dict[str, Any]) -> dict[str, float]:
    raw = payload.get("weighted_skills")
    if not isinstance(raw, list):
        return {}
    weight_map: dict[str, float] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("skill_name") or item.get("name")
        if not isinstance(name, str):
            continue
        canonical = name.strip().lower()
        if not canonical:
            continue
        weight = item.get("weight")
        if not isinstance(weight, int | float):
            continue
        weight_map[canonical] = float(weight)
    return weight_map


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
    return normalize_string_list(values)
