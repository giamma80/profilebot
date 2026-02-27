"""Job matching orchestrator — connects JD analysis, search, and LLM ranking."""

from __future__ import annotations

import logging
import time
from typing import Any

from src.core.config import Settings, get_settings
from src.core.llm.client import LLMDecisionClient, create_llm_client
from src.core.llm.schemas import LLMRequest
from src.services.matching.job_analyzer import analyze_job_description
from src.services.matching.schemas import (
    CandidateMatch,
    JDAnalysis,
    JobMatchRequest,
    JobMatchResponse,
)
from src.services.search.skill_search import (
    ProfileMatch,
    SearchDependencies,
    SearchFilters,
    search_by_skills,
)

logger = logging.getLogger(__name__)

# Maximum candidates sent to the LLM for ranking
_LLM_SHORTLIST_SIZE = 7

RANKING_SYSTEM_PROMPT = (
    "Sei un assistente per il matching professionale IT.\n"
    "La selezione deve basarsi PRINCIPALMENTE sulle skill.\n"
    "Le esperienze servono solo come supporto.\n"
    "Tutti i profili forniti sono già pre-filtrati per disponibilità.\n"
    "Non inventare skill non dichiarate.\n"
    "Rispondi esclusivamente in JSON."
)

RANKING_USER_PROMPT = (
    "Requisiti posizione:\n"
    "  Must-have: {must_have}\n"
    "  Nice-to-have: {nice_to_have}\n"
    "  Seniority: {seniority}\n\n"
    "Candidati:\n{candidates_context}\n\n"
    "Per ogni candidato valuta:\n"
    "1. score (0.0-1.0): quanto il profilo copre i requisiti\n"
    "2. matched_skills: skill possedute che matchano\n"
    "3. missing_skills: skill richieste ma assenti\n"
    "4. explanation: motivazione breve (2-3 frasi)\n"
    "5. strengths: punti di forza (max 3)\n"
    "6. gaps: lacune (max 3)\n\n"
    "Ordina dal migliore al peggiore.\n"
    'Rispondi in JSON: {{"rankings": [{{...}}, ...]}}'
)


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

    # Step 2: Vector search for candidates
    logger.info("Step 2/3: Searching candidates for skills: %s", jd_analysis.all_skills)
    search_filters = SearchFilters(availability=request.availability_filter)
    search_response = search_by_skills(
        skills=jd_analysis.all_skills,
        filters=search_filters,
        limit=_LLM_SHORTLIST_SIZE,
        dependencies=search_deps,
    )

    if not search_response.results:
        elapsed = int((time.perf_counter() - start) * 1000)
        return JobMatchResponse(
            extracted_requirements=jd_analysis.to_requirements(),
            candidates=[],
            no_match_reason="Nessun profilo trovato con le skill richieste e la disponibilità selezionata.",
            query_time_ms=elapsed,
        )

    # Step 3: LLM ranking (optional)
    if request.include_explanation:
        logger.info("Step 3/3: LLM ranking %d candidates", len(search_response.results))
        candidates = _llm_rank(
            jd_analysis=jd_analysis,
            search_results=search_response.results,
            settings=resolved_settings,
            client=llm_client_instance,
            max_candidates=request.max_candidates,
        )
    else:
        logger.info("Step 3/3: Skipping LLM ranking (include_explanation=False)")
        candidates = _search_only_rank(search_response.results, request.max_candidates)

    elapsed = int((time.perf_counter() - start) * 1000)
    return JobMatchResponse(
        extracted_requirements=jd_analysis.to_requirements(),
        candidates=candidates,
        query_time_ms=elapsed,
    )


def _llm_rank(
    *,
    jd_analysis: JDAnalysis,
    search_results: list[ProfileMatch],
    settings: Settings,
    client: Any | None,
    max_candidates: int,
) -> list[CandidateMatch]:
    """Rank candidates using the LLM decision engine."""
    llm = LLMDecisionClient(
        client=client or create_llm_client(settings),
        settings=settings,
    )

    candidates_context = _build_candidates_context(search_results)
    user_prompt = RANKING_USER_PROMPT.format(
        must_have=", ".join(jd_analysis.must_have) or "N/A",
        nice_to_have=", ".join(jd_analysis.nice_to_have) or "N/A",
        seniority=jd_analysis.seniority,
        candidates_context=candidates_context,
    )

    request = LLMRequest(
        system_prompt=RANKING_SYSTEM_PROMPT,
        context="",
        user_prompt=user_prompt,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )

    try:
        raw = _call_llm_for_ranking(llm, request)
        return _parse_ranking_output(raw, search_results, max_candidates)
    except (ValueError, KeyError) as exc:
        logger.warning("LLM ranking failed, falling back to search-only: %s", exc)
        return _search_only_rank(search_results, max_candidates)


def _build_candidates_context(results: list[ProfileMatch]) -> str:
    """Format search results as text context for LLM."""
    blocks: list[str] = []
    for i, match in enumerate(results, 1):
        skills = ", ".join(match.matched_skills) if match.matched_skills else "N/A"
        missing = ", ".join(match.missing_skills) if match.missing_skills else "nessuna"
        block = (
            f"--- Candidato {i} ---\n"
            f"CV_ID: {match.cv_id}\n"
            f"RES_ID: {match.res_id}\n"
            f"SCORE: {match.score:.2f}\n"
            f"SKILL MATCHATE: {skills}\n"
            f"SKILL MANCANTI: {missing}\n"
            f"SENIORITY: {match.seniority or 'unknown'}\n"
            f"DOMAIN: {match.skill_domain or 'N/A'}"
        )
        blocks.append(block)
    return "\n\n".join(blocks)


def _call_llm_for_ranking(llm: LLMDecisionClient, request: LLMRequest) -> str:
    """Call LLM for ranking and return raw JSON string."""
    model = llm._settings.llm_model
    response = llm._client.chat.completions.create(
        model=model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        messages=[
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.user_prompt},
        ],
        response_format={"type": "json_object"},
    )
    message = response.choices[0].message
    if not message or not message.content:
        raise ValueError("LLM ranking response is empty")
    return str(message.content)


def _parse_ranking_output(
    raw: str,
    search_results: list[ProfileMatch],
    max_candidates: int,
) -> list[CandidateMatch]:
    """Parse LLM ranking JSON into CandidateMatch list."""
    import json

    payload = json.loads(raw)
    rankings = payload.get("rankings", [])

    # Build lookup for res_id from search results
    cv_to_res: dict[str, int] = {m.cv_id: m.res_id for m in search_results}

    candidates: list[CandidateMatch] = []
    for entry in rankings[:max_candidates]:
        cv_id = str(entry.get("cv_id", ""))
        if cv_id not in cv_to_res:
            logger.warning("LLM returned unknown cv_id '%s', skipping", cv_id)
            continue

        score = float(entry.get("score", 0.0))
        # Normalize score to 0-1 range if LLM returned 0-100
        if score > 1.0:
            score = score / 100.0
        score = max(0.0, min(1.0, score))

        candidates.append(
            CandidateMatch(
                cv_id=cv_id,
                res_id=cv_to_res[cv_id],
                overall_score=score,
                matched_skills=_safe_str_list(
                    entry.get("matched_skills", entry.get("matched", []))
                ),
                missing_skills=_safe_str_list(
                    entry.get("missing_skills", entry.get("missing", []))
                ),
                explanation=str(entry.get("explanation", "")),
                strengths=_safe_str_list(entry.get("strengths", [])),
                gaps=_safe_str_list(entry.get("gaps", [])),
            )
        )

    return candidates


def _search_only_rank(
    results: list[ProfileMatch],
    max_candidates: int,
) -> list[CandidateMatch]:
    """Convert search results to CandidateMatch without LLM explanations."""
    return [
        CandidateMatch(
            cv_id=m.cv_id,
            res_id=m.res_id,
            overall_score=m.score,
            matched_skills=m.matched_skills,
            missing_skills=m.missing_skills,
        )
        for m in results[:max_candidates]
    ]


def _safe_str_list(value: Any) -> list[str]:
    """Safely convert to list of strings."""
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


__all__ = ["match_job"]
