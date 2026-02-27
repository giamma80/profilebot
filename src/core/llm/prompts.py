"""Prompt templates and context builder for the LLM decision engine."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import cast

from pydantic import ValidationError

from src.core.llm.schemas import DecisionCandidate, DecisionOutput

MAX_DECISION_CANDIDATES = 7


def build_system_prompt() -> str:
    """Return the system prompt for skill-first decision making."""
    return (
        "Sei un assistente per il matching professionale.\n"
        "La selezione deve basarsi principalmente sulle skill.\n"
        "Le esperienze servono solo come supporto.\n"
        "Tutti i profili forniti sono già disponibili e validi.\n"
        "Non inferire skill non dichiarate.\n"
        "Restituisci sempre il cv_id e una motivazione.\n"
        "Rispondi esclusivamente in JSON con i campi richiesti."
    )


def build_user_prompt() -> str:
    """Return the user prompt for selecting the best candidate."""
    return (
        "Dato il contesto fornito:\n"
        "- identifica il profilo più adatto\n"
        "- motiva la scelta dando priorità alle skill\n"
        "- indica eventuali gap rilevanti\n"
        "Rispondi in JSON con: selected_cv_id, decision_reason, matched_skills, "
        "missing_skills, confidence."
    )


def build_context(candidates: Iterable[DecisionCandidate]) -> str:
    """Build the context string for the LLM from shortlisted candidates."""
    normalized = list(candidates)
    _validate_candidates(normalized)

    blocks: list[str] = []
    for candidate in normalized:
        skills = ", ".join(candidate.skills) if candidate.skills else "N/A"
        experiences = _format_experiences(candidate.experience_summaries)

        block = (
            f"CV_ID: {candidate.cv_id}\n"
            f"SKILLS: {skills}\n"
            f"SENIORITY: {candidate.seniority}\n"
            f"YEARS_EXPERIENCE: {candidate.years_experience or 'N/A'}\n"
            f"AVAILABILITY: {candidate.availability_status}\n"
            f"EXPERIENCES (support):\n{experiences}"
        )
        blocks.append(block)
    return "\n\n".join(blocks).strip()


def _format_experiences(experiences: list[str]) -> str:
    if not experiences:
        return "* N/A"
    return "\n".join(f"* {experience}" for experience in experiences)


def _validate_candidates(candidates: list[DecisionCandidate]) -> None:
    if not candidates:
        raise ValueError("At least one candidate is required to build context")
    if len(candidates) > MAX_DECISION_CANDIDATES:
        raise ValueError(
            f"Context cannot include more than {MAX_DECISION_CANDIDATES} candidates",
        )

    seen: set[str] = set()
    for candidate in candidates:
        cv_id = candidate.cv_id.strip()
        if not cv_id:
            raise ValueError("Candidate cv_id cannot be empty")
        if cv_id in seen:
            raise ValueError(f"Duplicate cv_id in candidates: {cv_id}")
        seen.add(cv_id)


def parse_decision_output(
    raw_content: str,
    *,
    valid_cv_ids: set[str] | None = None,
) -> DecisionOutput:
    """Parse and validate the LLM JSON response.

    Args:
        raw_content: Raw JSON string from LLM.
        valid_cv_ids: Optional set of cv_ids from the shortlist.
            If provided, validates that selected_cv_id is in the set.

    Returns:
        Validated DecisionOutput.

    Raises:
        ValueError: If JSON is invalid, schema doesn't match,
            or selected_cv_id is not in the shortlist.
    """
    try:
        payload = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM response is not valid JSON") from exc

    try:
        output = DecisionOutput.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("LLM response does not match DecisionOutput schema") from exc

    # AP-5 guardrail: verify selected_cv_id is in the shortlist
    if valid_cv_ids is not None and output.selected_cv_id not in valid_cv_ids:
        raise ValueError(
            f"LLM selected cv_id '{output.selected_cv_id}' "
            f"not in shortlist: {sorted(valid_cv_ids)}"
        )

    return cast(DecisionOutput, output)
