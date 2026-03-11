"""Job matching orchestrator — connects JD analysis, search, and LLM ranking."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

from src.core.config import Settings, get_settings
from src.core.skills.dictionary import load_skill_dictionary
from src.core.skills.normalizer import SkillNormalizer
from src.services.matching.candidate_ranker import rank_candidates, search_only_rank
from src.services.matching.job_analyzer import analyze_job_description
from src.services.matching.schemas import JobMatchRequest, JobMatchResponse
from src.services.search.skill_search import (
    SearchDependencies,
    SearchFilters,
    search_by_skills,
)

logger = logging.getLogger(__name__)

# Maximum candidates sent to the LLM for ranking
_LLM_SHORTLIST_SIZE = 7
_DEFAULT_DICTIONARY_PATH = "data/skills_dictionary.yaml"


def _resolve_dictionary_path() -> Path:
    env_path = os.getenv("SKILLS_DICTIONARY_PATH")
    return Path(env_path or _DEFAULT_DICTIONARY_PATH)


def _normalize_skills(skills: list[str]) -> list[str]:
    dictionary = load_skill_dictionary(_resolve_dictionary_path())
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


def match_job(
    request: JobMatchRequest,
    *,
    settings: Settings | None = None,
    llm_client_instance: Any | None = None,
    search_deps: SearchDependencies | None = None,
) -> JobMatchResponse:
    """Execute the full job matching pipeline.

    Flow:
        1. LLM extracts skills from JD
        2. Vector search finds candidate profiles
        3. LLM ranks and explains top candidates

    Args:
        request: Job match request with JD text and params.
        settings: Optional application settings.
        llm_client_instance: Optional preconfigured OpenAI client.
        search_deps: Optional search dependencies for testing.

    Returns:
        JobMatchResponse with extracted requirements and ranked candidates.
    """
    resolved_settings = settings or get_settings()
    start = time.perf_counter()

    # Step 1: Extract skills from JD
    logger.info("Step 1/3: Analyzing job description (%d chars)", len(request.job_description))
    jd_analysis = analyze_job_description(
        request.job_description,
        settings=resolved_settings,
        client=llm_client_instance,
    )
    logger.info(
        "JD analysis: %d must-have, %d nice-to-have skills",
        len(jd_analysis.must_have),
        len(jd_analysis.nice_to_have),
    )

    if not jd_analysis.all_skills:
        elapsed = int((time.perf_counter() - start) * 1000)
        return JobMatchResponse(
            extracted_requirements=jd_analysis.to_requirements(),
            candidates=[],
            no_match_reason="Nessuna skill riconosciuta nella job description.",
            query_time_ms=elapsed,
        )

    normalized_must_have = _normalize_skills(jd_analysis.must_have)

    # Step 2: Vector search for candidates
    logger.info("Step 2/3: Searching candidates for skills: %s", jd_analysis.all_skills)
    search_filters = SearchFilters(availability=request.availability_filter)
    try:
        search_response = search_by_skills(
            skills=jd_analysis.all_skills,
            filters=search_filters,
            limit=_LLM_SHORTLIST_SIZE,
            dependencies=search_deps,
        )
    except ValueError as exc:
        logger.warning("Search skipped due to invalid skills: %s", exc)
        elapsed = int((time.perf_counter() - start) * 1000)
        return JobMatchResponse(
            extracted_requirements=jd_analysis.to_requirements(),
            candidates=[],
            no_match_reason="Nessuna skill valida riconosciuta nella job description.",
            query_time_ms=elapsed,
        )

    if not search_response.results:
        elapsed = int((time.perf_counter() - start) * 1000)
        return JobMatchResponse(
            extracted_requirements=jd_analysis.to_requirements(),
            candidates=[],
            no_match_reason="Nessun profilo trovato con le skill richieste e la disponibilità selezionata.",
            query_time_ms=elapsed,
        )

    filtered_results = search_response.results
    if normalized_must_have:
        must_have_set = set(normalized_must_have)
        filtered_results = [
            match for match in filtered_results if must_have_set.issubset(set(match.matched_skills))
        ]

    if not filtered_results:
        elapsed = int((time.perf_counter() - start) * 1000)
        return JobMatchResponse(
            extracted_requirements=jd_analysis.to_requirements(),
            candidates=[],
            no_match_reason="Nessun profilo trovato con tutte le skill must-have richieste.",
            query_time_ms=elapsed,
        )

    # Step 3: LLM ranking (optional)
    if request.include_explanation:
        logger.info("Step 3/3: LLM ranking %d candidates", len(filtered_results))
        candidates = rank_candidates(
            jd_analysis=jd_analysis,
            search_results=filtered_results,
            settings=resolved_settings,
            client=llm_client_instance,
            max_candidates=request.max_candidates,
        )
    else:
        logger.info("Step 3/3: Skipping LLM ranking (include_explanation=False)")
        candidates = search_only_rank(filtered_results, request.max_candidates)

    elapsed = int((time.perf_counter() - start) * 1000)
    return JobMatchResponse(
        extracted_requirements=jd_analysis.to_requirements(),
        candidates=candidates,
        query_time_ms=elapsed,
    )


__all__ = ["match_job"]
