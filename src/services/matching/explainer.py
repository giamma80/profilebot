"""Ranking explainer to parse LLM output for job matching."""

from __future__ import annotations

import json
import logging
from typing import Any

from src.services.matching.schemas import CandidateMatch
from src.services.search.skill_search import ProfileMatch

logger = logging.getLogger(__name__)


def parse_ranking_output(
    raw: str,
    search_results: list[ProfileMatch],
    max_candidates: int,
) -> list[CandidateMatch]:
    """Parse LLM ranking JSON into CandidateMatch list.

    Args:
        raw: Raw JSON string from the LLM.
        search_results: Search results used to build the shortlist.
        max_candidates: Maximum number of candidates to return.

    Returns:
        List of CandidateMatch objects, filtered to known cv_id values.
    """
    payload = json.loads(raw)
    rankings = payload.get("rankings", [])

    cv_to_match: dict[str, ProfileMatch] = {match.cv_id: match for match in search_results}
    candidates: list[CandidateMatch] = []

    for entry in rankings[:max_candidates]:
        cv_id = str(entry.get("cv_id", ""))
        if cv_id not in cv_to_match:
            logger.warning("LLM returned unknown cv_id '%s', skipping", cv_id)
            continue

        match = cv_to_match[cv_id]
        score = _normalize_score(entry.get("score", 0.0))

        candidates.append(
            CandidateMatch(
                cv_id=cv_id,
                res_id=match.res_id,
                full_name=_extract_full_name(match),
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


def _extract_full_name(match: ProfileMatch) -> str | None:
    payload = match.payload or {}
    full_name = payload.get("full_name")
    if isinstance(full_name, str):
        text = full_name.strip()
        return text or None
    return None


def _normalize_score(value: Any) -> float:
    score = float(value) if value is not None else 0.0
    if score > 1.0:
        score = score / 100.0
    return max(0.0, min(1.0, score))


def _safe_str_list(value: Any) -> list[str]:
    """Safely convert a value to a list of non-empty strings."""
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


__all__ = ["parse_ranking_output"]
