from __future__ import annotations

from datetime import date

from src.core.parser.schemas import ExperienceItem
from src.core.seniority.calculator import (
    calculate_seniority_bucket,
    calculate_total_experience_years,
)


def test_calculate_seniority_bucket__junior_years__returns_junior() -> None:
    result = calculate_seniority_bucket(1, 2, ["Engineer"])
    assert result == "junior"


def test_calculate_seniority_bucket__mid_years__returns_mid() -> None:
    result = calculate_seniority_bucket(4, 8, ["Software Engineer"])
    assert result == "mid"


def test_calculate_seniority_bucket__senior_years__returns_senior() -> None:
    result = calculate_seniority_bucket(6, 5, ["Backend Engineer"])
    assert result == "senior"


def test_calculate_seniority_bucket__lead_role__returns_lead() -> None:
    result = calculate_seniority_bucket(8, 5, ["Tech Lead"])
    assert result == "lead"


def test_calculate_seniority_bucket__no_data__returns_unknown() -> None:
    result = calculate_seniority_bucket(None, 0, [])
    assert result == "unknown"


def test_calculate_total_experience_years__multiple_items__returns_sum() -> None:
    experiences = [
        ExperienceItem(
            company="Acme",
            role="Engineer",
            start_date=date(2020, 1, 1),
            end_date=date(2022, 1, 1),
            description="",
            is_current=False,
        ),
        ExperienceItem(
            company="Beta",
            role="Engineer",
            start_date=date(2022, 2, 1),
            end_date=date(2024, 2, 1),
            description="",
            is_current=False,
        ),
    ]

    total_years = calculate_total_experience_years(experiences)

    assert total_years == 4


def test_calculate_seniority_bucket__skill_boost__raises_bucket() -> None:
    result = calculate_seniority_bucket(None, 10, [])
    assert result == "mid"


def test_calculate_seniority_bucket__skill_count_high__returns_senior() -> None:
    result = calculate_seniority_bucket(None, 20, [])
    assert result == "senior"
