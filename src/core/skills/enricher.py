"""Skill metadata enrichment utilities."""

from __future__ import annotations

import re
from datetime import date
from difflib import SequenceMatcher
from typing import TypedDict

from src.core.parser.schemas import ExperienceItem
from src.core.skills.weight import SkillLevel

_DAYS_IN_YEAR = 365.0
_CERT_FUZZY_THRESHOLD = 0.7
_SHORT_SKILL_LENGTH_THRESHOLD = 3
_LEVEL_INTERMEDIATE_MIN_YEARS = 2.0
_LEVEL_SENIOR_MIN_YEARS = 5.0
_LEVEL_EXPERT_MIN_YEARS = 10.0


class SkillMetadata(TypedDict):
    years: float
    level: SkillLevel
    certified: bool


def enrich_skill_metadata(
    skill_name: str,
    experiences: list[ExperienceItem],
    certifications: list[str],
) -> SkillMetadata:
    """Enrich skill metadata using parsed experiences and certifications.

    Args:
        skill_name: Canonical skill name.
        experiences: Parsed experience items.
        certifications: Parsed certification strings.

    Returns:
        Skill metadata including years, level, and certification flag.
    """
    years = _estimate_years_for_skill(skill_name, experiences)
    certified = _check_certification(skill_name, certifications)
    level = _infer_level(years)
    return {"years": years, "level": level, "certified": certified}


def _estimate_years_for_skill(
    skill_name: str,
    experiences: list[ExperienceItem],
) -> float:
    normalized = _normalize_skill(skill_name)
    if not normalized:
        return 0.0

    total_days = 0
    for experience in experiences:
        description = experience.description or ""
        if not _matches_skill(normalized, description):
            continue
        duration_days = _experience_duration_days(experience)
        if duration_days is None:
            continue
        total_days += duration_days

    years = total_days / _DAYS_IN_YEAR
    return max(0.0, round(years, 2))


def _matches_skill(skill: str, text: str) -> bool:
    return skill in text.lower()


def _experience_duration_days(experience: ExperienceItem) -> int | None:
    if not experience.start_date:
        return None

    if experience.end_date:
        end_date = experience.end_date
    elif experience.is_current:
        end_date = date.today()
    else:
        return None

    delta_days = (end_date - experience.start_date).days
    if delta_days < 0:
        return None
    return delta_days


def _check_certification(skill_name: str, certifications: list[str]) -> bool:
    normalized = _normalize_skill(skill_name)
    if not normalized:
        return False

    for cert in certifications:
        cert_normalized = cert.strip().lower()
        if not cert_normalized:
            continue
        if len(normalized) < _SHORT_SKILL_LENGTH_THRESHOLD:
            if _word_boundary_match(normalized, cert_normalized):
                return True
            continue
        if normalized in cert_normalized:
            return True
        if _fuzzy_cert_match(normalized, cert_normalized):
            return True
    return False


def _word_boundary_match(skill: str, text: str) -> bool:
    pattern = rf"\b{re.escape(skill)}\b"
    return re.search(pattern, text) is not None


def _fuzzy_cert_match(skill: str, cert: str) -> bool:
    if SequenceMatcher(None, skill, cert).ratio() >= _CERT_FUZZY_THRESHOLD:
        return True
    tokens = [token for token in re.split(r"[^a-z0-9]+", cert) if token]
    return any(
        SequenceMatcher(None, skill, token).ratio() >= _CERT_FUZZY_THRESHOLD for token in tokens
    )


def _infer_level(years: float) -> SkillLevel:
    if years > _LEVEL_EXPERT_MIN_YEARS:
        return "expert"
    if years > _LEVEL_SENIOR_MIN_YEARS:
        return "senior"
    if years >= _LEVEL_INTERMEDIATE_MIN_YEARS:
        return "intermediate"
    return "junior"


def _normalize_skill(skill_name: str) -> str:
    return skill_name.strip().lower()
