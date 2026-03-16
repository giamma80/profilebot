"""Rule-based fallback for search context extraction."""

from __future__ import annotations

import os
import re
from pathlib import Path

from src.core.skills.dictionary import load_skill_dictionary
from src.core.skills.normalizer import SkillNormalizer
from src.services.search.schemas import SearchContext

TOKEN_RE = re.compile(r"[A-Za-z0-9#+./-]+")

SENIORITY_KEYWORDS = {
    "junior": "junior",
    "jr": "junior",
    "mid": "mid",
    "middle": "mid",
    "senior": "senior",
    "sr": "senior",
    "lead": "lead",
    "principal": "lead",
    "staff": "lead",
}

AVAILABILITY_KEYWORDS = (
    "disponibile",
    "availability",
    "available",
    "immediato",
    "immediatamente",
    "immediate",
    "asap",
    "subito",
)

DOMAIN_KEYWORDS = (
    "backend",
    "front-end",
    "frontend",
    "fullstack",
    "full-stack",
    "data",
    "devops",
    "cloud",
    "mobile",
)

DEFAULT_DICTIONARY_PATH = "data/skills_dictionary.yaml"


def _resolve_dictionary_path() -> Path:
    env_path = os.getenv("SKILLS_DICTIONARY_PATH")
    return Path(env_path or DEFAULT_DICTIONARY_PATH)


def build_fallback_search_context(query: str) -> SearchContext:
    """Build a fallback SearchContext using rule-based heuristics.

    Args:
        query: Raw query string.

    Returns:
        Best-effort SearchContext with nullable fields.
    """
    normalized_query = query.strip()
    extracted_skills = _extract_skills(normalized_query)
    return SearchContext(
        extracted_skills=extracted_skills or None,
        seniority=_extract_seniority(normalized_query),
        availability_required=_extract_availability(normalized_query),
        domain=_extract_domain(normalized_query),
        role=None,
        business_context=None,
        raw_query=query,
    )


def _extract_skills(query: str) -> list[str]:
    if not query:
        return []
    dictionary = load_skill_dictionary(_resolve_dictionary_path())
    normalizer = SkillNormalizer(dictionary)
    tokens = _tokenize(query)
    candidates = list(tokens)
    candidates.extend(_build_ngrams(tokens, n=2))

    extracted: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = normalizer.normalize(candidate)
        if normalized is None:
            continue
        canonical = normalized.canonical.strip().lower()
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        extracted.append(canonical)
    return extracted


def _extract_seniority(query: str) -> str | None:
    if not query:
        return None
    tokens = _tokenize(query)
    for token in tokens:
        if token in SENIORITY_KEYWORDS:
            return SENIORITY_KEYWORDS[token]
    return None


def _extract_availability(query: str) -> bool | None:
    if not query:
        return None
    lowered = query.lower()
    if any(keyword in lowered for keyword in AVAILABILITY_KEYWORDS):
        return True
    return None


def _extract_domain(query: str) -> str | None:
    if not query:
        return None
    lowered = query.lower()
    for keyword in DOMAIN_KEYWORDS:
        if keyword in lowered:
            return "frontend" if keyword in {"front-end", "frontend"} else keyword.replace("-", "")
    return None


def _tokenize(query: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(query)]


def _build_ngrams(tokens: list[str], *, n: int) -> list[str]:
    if n <= 1:
        return list(tokens)
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]
