"""JD skill extraction using LLM."""

from __future__ import annotations

import json
import logging
from typing import Any, cast

from pydantic import ValidationError

from src.core.config import Settings, get_settings
from src.core.llm.client import LLMDecisionClient, create_llm_client
from src.core.llm.schemas import LLMRequest
from src.services.matching.schemas import JDAnalysis

logger = logging.getLogger(__name__)

JD_EXTRACTION_SYSTEM_PROMPT = (
    "Sei un assistente specializzato nell'analisi di job description IT.\n"
    "Il tuo compito è estrarre le skill tecniche richieste dalla JD.\n"
    "Distingui tra skill obbligatorie (must_have) e preferenziali (nice_to_have).\n"
    "Usa nomi di skill standard e riconoscibili (es. 'Python', 'Kubernetes', 'React').\n"
    "Non inventare skill non menzionate nella JD.\n"
    "Rispondi esclusivamente in JSON."
)

JD_EXTRACTION_USER_PROMPT = (
    "Analizza la seguente Job Description ed estrai le skill richieste.\n\n"
    "Job Description:\n{job_description}\n\n"
    "Rispondi in JSON con:\n"
    "{{\n"
    '  "must_have": ["skill1", "skill2"],\n'
    '  "nice_to_have": ["skill3", "skill4"],\n'
    '  "seniority": "junior|mid|senior|any",\n'
    '  "domain": "backend|frontend|data|devops|management|null"\n'
    "}}"
)


def analyze_job_description(
    job_description: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> JDAnalysis:
    """Extract skill requirements from a job description using LLM.

    Args:
        job_description: Free-text job description.
        settings: Optional application settings.
        client: Optional preconfigured OpenAI-compatible client.

    Returns:
        JDAnalysis with must_have and nice_to_have skills.

    Raises:
        ValueError: If LLM response cannot be parsed.
    """
    resolved_settings = settings or get_settings()
    llm_client = LLMDecisionClient(
        client=client or create_llm_client(resolved_settings),
        settings=resolved_settings,
    )

    request = LLMRequest(
        system_prompt=JD_EXTRACTION_SYSTEM_PROMPT,
        context="",
        user_prompt=JD_EXTRACTION_USER_PROMPT.format(job_description=job_description),
        temperature=0.0,
        max_tokens=1000,
    )

    raw_content = _call_llm_raw(llm_client, request)
    return _parse_jd_analysis(raw_content)


def _call_llm_raw(llm_client: LLMDecisionClient, request: LLMRequest) -> str:
    """Call LLM and return raw content string (bypass DecisionOutput parsing)."""
    return llm_client.chat_completion_raw(request)


def _parse_jd_analysis(raw_content: str) -> JDAnalysis:
    """Parse LLM JSON response into JDAnalysis."""
    try:
        payload = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM JD analysis response is not valid JSON") from exc

    # Normalize: domain "null" string → None
    if payload.get("domain") in ("null", "None", ""):
        payload["domain"] = None

    try:
        return cast(JDAnalysis, JDAnalysis.model_validate(payload))
    except ValidationError as exc:
        logger.warning("JD analysis validation failed, attempting partial parse: %s", exc)
        return _fallback_parse(payload)


def _fallback_parse(payload: dict[str, Any]) -> JDAnalysis:
    """Best-effort parsing when strict validation fails."""
    must_have = _extract_string_list(payload.get("must_have", []))
    nice_to_have = _extract_string_list(payload.get("nice_to_have", []))

    if not must_have and not nice_to_have:
        raise ValueError("LLM extracted zero skills from job description")

    return JDAnalysis(
        must_have=must_have,
        nice_to_have=nice_to_have,
        seniority="any",
        domain=None,
    )


def _extract_string_list(value: Any) -> list[str]:
    """Safely extract a list of strings."""
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


__all__ = ["analyze_job_description"]
