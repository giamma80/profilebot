"""Seniority calculator heuristic."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Literal

from src.core.parser.schemas import ExperienceItem

SeniorityBucket = Literal["junior", "lead", "mid", "senior", "unknown"]

_LEAD_KEYWORDS = (
    "lead",
    "manager",
    "head",
    "director",
    "principal",
    "architect",
)

_YEARS_LEAD = 12
_YEARS_LEAD_WITH_KEYWORDS = 8
_YEARS_SENIOR = 6
_YEARS_MID = 3

_SKILL_COUNT_SENIOR = 20
_SKILL_COUNT_MID = 10
_SKILL_COUNT_JUNIOR = 1


def calculate_total_experience_years(
    experiences: Iterable[ExperienceItem],
) -> int | None:
    """Calculate total experience years across experiences.

    Args:
        experiences: Experience items to aggregate.

    Returns:
        Total years of experience, or None when no dates are available.
    """
    total_years = 0
    has_any = False
    for experience in experiences:
        years = _calc_experience_years(experience)
        if years is None:
            continue
        has_any = True
        total_years += years
    return total_years if has_any else None


def calculate_seniority_bucket(
    years_experience: int | None,
    skill_count: int,
    role_titles: Iterable[str],
    summary_text: str | None = None,
) -> SeniorityBucket:
    """Calculate seniority bucket using experience, skills, and role keywords.

    Args:
        years_experience: Total years of experience when available.
        skill_count: Number of normalized skills.
        role_titles: Role titles to inspect for seniority keywords.
        summary_text: Optional summary text to inspect for seniority keywords.

    Returns:
        Seniority bucket value.
    """
    bucket: SeniorityBucket = "unknown"
    has_titles = any(title.strip() for title in role_titles if title)
    has_summary = bool(summary_text and summary_text.strip())
    if years_experience is None and skill_count == 0 and not has_titles and not has_summary:
        bucket = "unknown"
    elif years_experience is None:
        if skill_count >= _SKILL_COUNT_SENIOR:
            bucket = "senior"
        elif skill_count >= _SKILL_COUNT_MID:
            bucket = "mid"
        elif skill_count >= _SKILL_COUNT_JUNIOR:
            bucket = "junior"
        else:
            bucket = "unknown"
    else:
        lead_keywords = _has_lead_keywords(role_titles, summary_text)
        if years_experience >= _YEARS_LEAD or (
            years_experience >= _YEARS_LEAD_WITH_KEYWORDS and lead_keywords
        ):
            bucket = "lead"
        elif years_experience >= _YEARS_SENIOR:
            bucket = "senior"
        elif years_experience >= _YEARS_MID:
            bucket = "mid"
        elif years_experience >= 0:
            bucket = "junior"
        else:
            bucket = "unknown"
    return bucket


def _calc_experience_years(experience: ExperienceItem) -> int | None:
    if experience.start_date and experience.end_date:
        delta_days = (experience.end_date - experience.start_date).days
        return delta_days // 365 if delta_days >= 0 else None
    if experience.start_date and experience.is_current:
        delta_days = (date.today() - experience.start_date).days
        return delta_days // 365 if delta_days >= 0 else None
    return None


def _normalize_text(parts: Iterable[str]) -> str:
    return " ".join(text.strip().lower() for text in parts if text and text.strip())


def _has_lead_keywords(role_titles: Iterable[str], summary_text: str | None) -> bool:
    combined = _normalize_text([*role_titles, summary_text or ""])
    if not combined:
        return False
    return any(keyword in combined for keyword in _LEAD_KEYWORDS)
