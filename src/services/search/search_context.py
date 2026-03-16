"""LLM-based search context extraction with rule-based fallback."""

from __future__ import annotations

import json
import logging
from typing import Any, cast

from pydantic import ValidationError

from src.core.config import Settings, get_settings
from src.core.llm.client import LLMDecisionClient, create_llm_client
from src.core.llm.schemas import LLMRequest
from src.services.search.schemas import SearchContext
from src.services.search.search_context_fallback import build_fallback_search_context

logger = logging.getLogger(__name__)

LLM_TIMEOUT_SECONDS = 2.0
LLM_MAX_TOKENS = 400
MAX_BUSINESS_CONTEXT_LENGTH = 200

SENIORITY_VALUES = {"junior", "mid", "senior", "lead"}
ROLE_VALUES = {
    "developer",
    "analyst",
    "architect",
    "project_manager",
    "tester",
    "devops",
    "data_scientist",
}

SYSTEM_PROMPT = (
    "Sei un assistente che estrae contesto strutturato da query di ricerca profili IT.\n"
    "Devi restituire SOLO un oggetto JSON con i campi richiesti.\n"
    "Non inventare informazioni: se un campo non è esplicitato, usa null.\n"
    "Limita business_context a massimo 200 caratteri.\n"
    "Valori ammessi:\n"
    "- seniority: junior | mid | senior | lead | null\n"
    "- availability_required: true | false | null\n"
    "- role: developer | analyst | architect | project_manager | tester | devops | data_scientist | null\n"
    "Normalizza domain con esempi: banking, finance, retail, telco.\n"
)

USER_PROMPT_TEMPLATE = (
    "Estrai il search_context dalla query:\n"
    '"{query}"\n\n'
    "Rispondi in JSON con le chiavi:\n"
    "{{\n"
    '  "extracted_skills": ["skill1", "skill2"] or null,\n'
    '  "seniority": "junior|mid|senior|lead|null",\n'
    '  "availability_required": true|false|null,\n'
    '  "domain": "string|null",\n'
    '  "role": "developer|analyst|architect|project_manager|tester|devops|data_scientist|null",\n'
    '  "business_context": "string|null",\n'
    '  "raw_query": "string"\n'
    "}}"
)


def extract_search_context(
    query: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> SearchContext | None:
    """Extract a structured SearchContext from a query string.

    Args:
        query: Raw search query.
        settings: Optional app settings override.
        client: Optional OpenAI-compatible client override.

    Returns:
        SearchContext when extraction succeeds, otherwise fallback or None.
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        return None

    resolved_settings = settings or get_settings()
    llm_client = LLMDecisionClient(
        client=client or _create_timeout_client(resolved_settings),
        settings=resolved_settings,
    )
    request = LLMRequest(
        system_prompt=SYSTEM_PROMPT,
        context="",
        user_prompt=USER_PROMPT_TEMPLATE.format(query=cleaned_query),
        temperature=0.0,
        max_tokens=LLM_MAX_TOKENS,
    )

    try:
        raw_content = llm_client.chat_completion_raw(request)
        payload = _parse_payload(raw_content, cleaned_query)
        return cast(SearchContext, SearchContext.model_validate(payload))
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        logger.warning("Search context parsing failed, using fallback: %s", exc)
    except Exception as exc:
        logger.warning("Search context LLM call failed, using fallback: %s", exc)

    try:
        return build_fallback_search_context(cleaned_query)
    except Exception as fallback_exc:
        logger.warning("Search context fallback failed: %s", fallback_exc)
        return None


def _create_timeout_client(settings: Settings) -> Any:
    return create_llm_client(settings, timeout=LLM_TIMEOUT_SECONDS)


def _parse_payload(raw_content: str, raw_query: str) -> dict[str, Any]:
    payload = json.loads(raw_content)
    if not isinstance(payload, dict):
        raise ValueError("Search context payload is not a JSON object")

    extracted_skills = _normalize_string_list(payload.get("extracted_skills"))
    seniority = _normalize_enum(payload.get("seniority"), SENIORITY_VALUES)
    availability_required = _normalize_bool(payload.get("availability_required"))
    domain = _normalize_optional_string(payload.get("domain"))
    role = _normalize_enum(payload.get("role"), ROLE_VALUES)
    business_context = _normalize_optional_string(payload.get("business_context"))
    if business_context and len(business_context) > MAX_BUSINESS_CONTEXT_LENGTH:
        business_context = business_context[:MAX_BUSINESS_CONTEXT_LENGTH]

    return {
        "extracted_skills": extracted_skills,
        "seniority": seniority,
        "availability_required": availability_required,
        "domain": domain,
        "role": role,
        "business_context": business_context,
        "raw_query": raw_query,
    }


def _normalize_string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    normalized = [str(item).strip() for item in value if str(item).strip()]
    return normalized or None


def _normalize_enum(value: Any, allowed: set[str]) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in {"null", "none", ""}:
            return None
        if cleaned in allowed:
            return cleaned
    return None


def _normalize_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in {"true", "yes"}:
            return True
        if cleaned in {"false", "no"}:
            return False
    return None


def _normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.lower() in {"null", "none"} or not cleaned:
            return None
        return cleaned
    return None


__all__ = ["extract_search_context"]
