"""Candidate ranking with LLM scoring and search-only fallback."""

from __future__ import annotations

import logging
from typing import Any

from src.core.config import Settings
from src.core.llm.client import LLMDecisionClient, create_llm_client
from src.core.llm.schemas import LLMRequest
from src.services.matching.explainer import parse_ranking_output
from src.services.matching.schemas import CandidateMatch, JDAnalysis
from src.services.search.skill_search import ProfileMatch

logger = logging.getLogger(__name__)

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
    'Rispondi in JSON: {"rankings": [{...}, ...]}'
)


def rank_candidates(
    *,
    jd_analysis: JDAnalysis,
    search_results: list[ProfileMatch],
    settings: Settings,
    client: Any | None,
    max_candidates: int,
) -> list[CandidateMatch]:
    """Rank candidates using the LLM decision engine.

    Args:
        jd_analysis: Parsed JD analysis with must/nice skills.
        search_results: Search results to rank.
        settings: Application settings.
        client: Optional preconfigured OpenAI client.
        max_candidates: Max candidates to return.

    Returns:
        Ranked candidates with explanations, fallback to search-only on errors.
    """
    llm = LLMDecisionClient(
        client=client or create_llm_client(settings),
        settings=settings,
    )

    candidates_context = build_candidates_context(search_results)
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
        return parse_ranking_output(raw, search_results, max_candidates)
    except (ValueError, KeyError) as exc:
        logger.warning("LLM ranking failed, falling back to search-only: %s", exc)
        return search_only_rank(search_results, max_candidates)


def build_candidates_context(results: list[ProfileMatch]) -> str:
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


def search_only_rank(
    results: list[ProfileMatch],
    max_candidates: int,
) -> list[CandidateMatch]:
    """Convert search results to CandidateMatch without LLM explanations."""
    return [
        CandidateMatch(
            cv_id=match.cv_id,
            res_id=match.res_id,
            overall_score=match.score,
            matched_skills=match.matched_skills,
            missing_skills=match.missing_skills,
        )
        for match in results[:max_candidates]
    ]


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


__all__ = [
    "build_candidates_context",
    "rank_candidates",
    "search_only_rank",
]
