"""Candidate ranking with LLM scoring and search-only fallback."""

from __future__ import annotations

import logging
from typing import Any, cast

from src.core.config import Settings
from src.core.knowledge_profile import KPBuilder, KPContextSerializer
from src.core.knowledge_profile.schemas import KnowledgeProfile
from src.core.llm.client import LLMDecisionClient, create_llm_client
from src.core.llm.schemas import LLMRequest
from src.core.seniority.calculator import SeniorityBucket
from src.services.matching.explainer import parse_ranking_output
from src.services.matching.schemas import CandidateMatch, JDAnalysis
from src.services.search.skill_search import ProfileMatch

logger = logging.getLogger(__name__)

_KP_SERIALIZER_CONFIGS = (
    {
        "max_skills_per_domain": 10,
        "max_experiences": 3,
        "max_chunks": 3,
        "max_chunk_chars": 300,
    },
    {
        "max_skills_per_domain": 7,
        "max_experiences": 2,
        "max_chunks": 2,
        "max_chunk_chars": 220,
    },
    {
        "max_skills_per_domain": 5,
        "max_experiences": 1,
        "max_chunks": 1,
        "max_chunk_chars": 160,
    },
)

RANKING_SYSTEM_PROMPT = (
    "Sei un assistente per il matching professionale IT.\n"
    "La selezione deve basarsi PRINCIPALMENTE sulle skill.\n"
    "Le esperienze servono solo come supporto.\n"
    "I candidati sono forniti in formato Knowledge Profile con sezioni strutturate.\n"
    "Usa disponibilità, reskilling, IC sub-state e skill per domain per la valutazione.\n"
    "Non inventare skill non dichiarate.\n"
    "Rispondi esclusivamente in JSON."
)

RANKING_USER_PROMPT = (
    "Requisiti posizione:\n"
    "  Must-have: {must_have}\n"
    "  Nice-to-have: {nice_to_have}\n"
    "  Seniority: {seniority}\n\n"
    "Candidati (Knowledge Profile):\n{candidates_context}\n\n"
    "Per ogni candidato valuta usando le sezioni strutturate:\n"
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

    candidates_context = build_candidates_context_structured(
        jd_analysis=jd_analysis,
        search_results=search_results,
        settings=settings,
    )
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


def build_candidates_context_flat(results: list[ProfileMatch]) -> str:
    """Format search results as text context for LLM (flat)."""
    blocks = [_build_flat_block(match, index=index) for index, match in enumerate(results, start=1)]
    return "\n\n".join(blocks)


def build_candidates_context(results: list[ProfileMatch]) -> str:
    """Deprecated: use build_candidates_context_flat instead."""
    logger.warning("build_candidates_context is deprecated; use build_candidates_context_flat")
    return build_candidates_context_flat(results)


def _coerce_seniority_bucket(value: str | None) -> SeniorityBucket | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized in {"junior", "mid", "senior", "lead", "unknown"}:
        return cast(SeniorityBucket, normalized)
    return None


def build_candidates_context_structured(
    *,
    jd_analysis: JDAnalysis,
    search_results: list[ProfileMatch],
    settings: Settings,
) -> str:
    """Build Knowledge Profile context with per-candidate fallback."""
    builder = KPBuilder()
    profiles: list[KnowledgeProfile | None] = []
    for match in search_results:
        try:
            profile = builder.build_from_search(
                cv_id=match.cv_id,
                res_id=match.res_id,
                payload=match.payload or {},
                query_skills=jd_analysis.all_skills,
                match_score=match.score,
                matched_skills=match.matched_skills,
                missing_skills=match.missing_skills,
                seniority_bucket=_coerce_seniority_bucket(match.seniority),
            )
            if profile.availability is None:
                # TODO: make availability requirement configurable (e.g., Settings.kp_require_availability).
                raise ValueError("Availability not available")
            profiles.append(profile)
        except Exception as exc:
            logger.warning("KP context fallback for cv_id '%s': %s", match.cv_id, exc)
            profiles.append(None)

    total = len(search_results)
    token_budget = int(settings.llm_max_tokens * 0.6)
    last_context = ""
    for config in _KP_SERIALIZER_CONFIGS:
        serializer = KPContextSerializer(**config)
        blocks: list[str] = []
        for index, (match, profile_item) in enumerate(
            zip(search_results, profiles, strict=False), start=1
        ):
            if profile_item is None:
                blocks.append(_build_flat_block(match, index=index))
            else:
                blocks.append(serializer.serialize(profile_item, index=index, total=total))
        context = "\n\n".join(blocks)
        last_context = context
        if token_budget <= 0:
            return context
        if KPContextSerializer.estimate_tokens(context) <= token_budget:
            return context

    logger.warning(
        "KP context exceeds token budget (%s tokens), using most compact config",
        token_budget,
    )
    return last_context


def _build_flat_block(match: ProfileMatch, *, index: int) -> str:
    skills = ", ".join(match.matched_skills) if match.matched_skills else "N/A"
    missing = ", ".join(match.missing_skills) if match.missing_skills else "nessuna"
    return (
        f"--- Candidato {index} ---\n"
        f"CV_ID: {match.cv_id}\n"
        f"RES_ID: {match.res_id}\n"
        f"SCORE: {match.score:.2f}\n"
        f"SKILL MATCHATE: {skills}\n"
        f"SKILL MANCANTI: {missing}\n"
        f"SENIORITY: {match.seniority or 'unknown'}\n"
        f"DOMAIN: {match.skill_domain or 'N/A'}"
    )


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
    "build_candidates_context_flat",
    "build_candidates_context_structured",
    "rank_candidates",
    "search_only_rank",
]
