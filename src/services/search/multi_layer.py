"""Multi-layer search orchestrator combining skill and chunk search."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import cast

from src.core.config import get_settings
from src.core.search.fusion import rrf_fuse
from src.core.skills.dictionary import load_skill_dictionary
from src.services.search.chunk_search import search_by_chunks
from src.services.search.metrics import CHUNK_RESULTS, FUSION_USED
from src.services.search.skill_search import (
    ProfileMatch,
    SearchFilters,
    SkillSearchResponse,
    _normalize_query_skills,
    _resolve_dictionary_path,
    search_by_skills,
)


@dataclass(frozen=True)
class MetadataContext:
    skills: list[str]
    skill_response: SkillSearchResponse
    candidates_by_skills: list[ProfileMatch]
    candidates_by_chunks: list[ProfileMatch]
    fusion_applied: bool
    elapsed_ms: int


ELIGIBILITY_MATCH_RATIO_THRESHOLD = 0.4


def multi_layer_search(
    skills: list[str],
    *,
    filters: SearchFilters | None = None,
    limit: int = 10,
    offset: int = 0,
) -> SkillSearchResponse:
    """Search profiles using multi-layer orchestration with fusion and eligibility filtering.

    Args:
        skills: Raw skill strings from the request.
        filters: Optional filter constraints.
        limit: Maximum number of results to return.
        offset: Result offset for pagination.

    Returns:
        Search response with skill, chunk, and fused candidates.
    """
    start_time = time.perf_counter()
    fetch_limit = max(0, limit) + max(0, offset)

    skills_response = search_by_skills(
        skills=skills,
        filters=filters,
        limit=fetch_limit,
        offset=0,
    )
    chunks_response = search_by_chunks(
        query_text=" ".join(skills),
        filters=filters,
        limit=fetch_limit,
        offset=0,
    )

    candidates_by_skills = skills_response.results
    candidates_by_chunks = chunks_response.results

    CHUNK_RESULTS.inc(len(candidates_by_chunks))

    fused_candidates = cast(
        list[ProfileMatch],
        rrf_fuse(primary=candidates_by_skills, secondary=candidates_by_chunks),
    )
    fusion_applied = bool(candidates_by_skills or candidates_by_chunks)
    if fusion_applied:
        FUSION_USED.inc()

    eligible_fused = _filter_by_eligibility(fused_candidates, candidates_by_skills)

    paged_skills = _paginate(candidates_by_skills, limit, offset)
    paged_chunks = _paginate(candidates_by_chunks, limit, offset)
    paged_fused = _paginate(eligible_fused, limit, offset)

    results = paged_fused if fusion_applied else paged_skills
    total = len(eligible_fused) if fusion_applied else len(candidates_by_skills)
    no_match_reason = (
        "below_eligibility_threshold" if fusion_applied and not eligible_fused else None
    )
    fusion_strategy = "rrf" if fusion_applied else None

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    search_metadata = _build_search_metadata(
        MetadataContext(
            skills=skills,
            skill_response=skills_response,
            candidates_by_skills=candidates_by_skills,
            candidates_by_chunks=candidates_by_chunks,
            fusion_applied=fusion_applied,
            elapsed_ms=elapsed_ms,
        )
    )

    return SkillSearchResponse(
        results=results,
        total=total,
        limit=limit,
        offset=offset,
        query_time_ms=elapsed_ms,
        candidates_by_skills=paged_skills,
        candidates_by_chunks=paged_chunks,
        candidates_fused=paged_fused if fusion_applied else None,
        fallback_activated=skills_response.fallback_activated,
        recovered_skills=skills_response.recovered_skills,
        no_match_reason=no_match_reason,
        fusion_strategy=fusion_strategy,
        search_metadata=search_metadata,
    )


def _paginate(items: list[ProfileMatch], limit: int, offset: int) -> list[ProfileMatch]:
    if limit <= 0:
        return []
    start = max(0, offset)
    end = start + limit
    return items[start:end]


def _filter_by_eligibility(
    fused_candidates: list[ProfileMatch],
    skill_candidates: list[ProfileMatch],
) -> list[ProfileMatch]:
    match_ratios = _build_match_ratio_map(skill_candidates)
    return [
        candidate for candidate in fused_candidates if _is_eligible(candidate.cv_id, match_ratios)
    ]


def _build_match_ratio_map(skill_candidates: list[ProfileMatch]) -> dict[str, float]:
    ratios: dict[str, float] = {}
    for candidate in skill_candidates:
        matched = len(candidate.matched_skills)
        missing = len(candidate.missing_skills)
        total = matched + missing
        ratios[candidate.cv_id] = (matched / total) if total else 0.0
    return ratios


def _is_eligible(cv_id: str, match_ratios: dict[str, float]) -> bool:
    return match_ratios.get(cv_id, 0.0) >= ELIGIBILITY_MATCH_RATIO_THRESHOLD


def _normalize_query_skills_for_metadata(skills: list[str]) -> list[str]:
    dictionary = load_skill_dictionary(_resolve_dictionary_path())
    return _normalize_query_skills(skills, dictionary)


def _build_search_metadata(context: MetadataContext) -> dict[str, object]:
    skills = context.skills
    skill_response = context.skill_response
    candidates_by_skills = context.candidates_by_skills
    candidates_by_chunks = context.candidates_by_chunks
    fusion_applied = context.fusion_applied
    elapsed_ms = context.elapsed_ms

    normalized_skills = _normalize_query_skills_for_metadata(skills)
    recovered_skills = skill_response.recovered_skills or []
    if skill_response.fallback_activated and recovered_skills:
        normalized_skills = recovered_skills

    layers_used = ["skill_search", "chunk_search"]
    if skill_response.fallback_activated:
        layers_used.append("skills_dictionary_fallback")

    settings = get_settings()
    scoring_formula = "weighted_v2" if settings.scoring_use_weighted else "legacy_0.7_0.3"
    total_candidates = len(
        {candidate.cv_id for candidate in candidates_by_skills}.union(
            {candidate.cv_id for candidate in candidates_by_chunks}
        )
    )

    return {
        "query_skills_raw": skills,
        "query_skills_normalized": normalized_skills,
        "query_skills_recovered": recovered_skills if skill_response.fallback_activated else [],
        "layers_used": layers_used,
        "scoring_formula": scoring_formula,
        "total_candidates_evaluated": total_candidates,
        "fusion_applied": fusion_applied,
        "elapsed_ms": elapsed_ms,
    }
