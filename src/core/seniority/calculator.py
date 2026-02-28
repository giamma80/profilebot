"""Seniority calculator heuristic."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Literal

from src.core.parser.schemas import ExperienceItem

SeniorityBucket = Literal["junior", "lead", "mid", "senior", "unknown"]

_LEAD_KEYWORDS = (
    "lead",
    "principal",
    "manager",
    "head",
    "director",
    "staff",
    "architect",
    "cto",
    "vp",
    "chief",
    "tech lead",
    "team lead",
)
_SENIOR_KEYWORDS = ("senior", "sr")
_MID_KEYWORDS = ("mid", "intermediate")
_JUNIOR_KEYWORDS = ("junior", "jr", "intern", "entry")

_SKILL_BOOST_HIGH = 25
_SKILL_BOOST_MEDIUM = 15
_JUNIOR_MAX_YEARS = 3
_MID_MAX_YEARS = 7
_SENIOR_MAX_YEARS = 12


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
) -> SeniorityBucket:
    """Calculate seniority bucket using experience, skills, and role keywords.

    Args:
        years_experience: Total years of experience when available.
        skill_count: Number of normalized skills.
        role_titles: Role titles to inspect for seniority keywords.

    Returns:
        Seniority bucket value.
    """
    role_floor = _role_floor(role_titles)
    if years_experience is None and role_floor is None and skill_count == 0:
        return "unknown"

    base_years = years_experience or 0
    score_years = base_years + _skill_boost(skill_count) + _role_boost(role_floor)
    bucket = _bucket_from_score(score_years)
    if role_floor is not None:
        return _max_bucket(bucket, role_floor)
    return bucket


def _calc_experience_years(experience: ExperienceItem) -> int | None:
    if experience.start_date and experience.end_date:
        delta_days = (experience.end_date - experience.start_date).days
        return delta_days // 365 if delta_days >= 0 else None
    if experience.start_date and experience.is_current:
        delta_days = (date.today() - experience.start_date).days
        return delta_days // 365 if delta_days >= 0 else None
    return None


def _normalize_titles(role_titles: Iterable[str]) -> list[str]:
    return [title.strip().lower() for title in role_titles if title and title.strip()]


def _role_floor(role_titles: Iterable[str]) -> SeniorityBucket | None:
    titles = _normalize_titles(role_titles)
    if _has_keyword(titles, _LEAD_KEYWORDS):
        return "lead"
    if _has_keyword(titles, _SENIOR_KEYWORDS):
        return "senior"
    if _has_keyword(titles, _MID_KEYWORDS):
        return "mid"
    if _has_keyword(titles, _JUNIOR_KEYWORDS):
        return "junior"
    return None


def _has_keyword(titles: Iterable[str], keywords: Iterable[str]) -> bool:
    return any(keyword in title for title in titles for keyword in keywords)


def _skill_boost(skill_count: int) -> int:
    if skill_count >= _SKILL_BOOST_HIGH:
        return 2
    if skill_count >= _SKILL_BOOST_MEDIUM:
        return 1
    return 0


def _role_boost(role_floor: SeniorityBucket | None) -> int:
    if role_floor == "lead":
        return 4
    if role_floor == "senior":
        return 2
    if role_floor == "mid":
        return 1
    if role_floor == "junior":
        return -1
    return 0


def _bucket_from_score(score_years: int) -> SeniorityBucket:
    if score_years < _JUNIOR_MAX_YEARS:
        return "junior"
    if score_years < _MID_MAX_YEARS:
        return "mid"
    if score_years < _SENIOR_MAX_YEARS:
        return "senior"
    return "lead"


def _max_bucket(a: SeniorityBucket, b: SeniorityBucket) -> SeniorityBucket:
    rank = {"unknown": 0, "junior": 1, "mid": 2, "senior": 3, "lead": 4}
    return a if rank[a] >= rank[b] else b
