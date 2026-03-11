from __future__ import annotations

from datetime import date

import pytest

from src.core.parser.schemas import ExperienceItem
from src.core.skills.enricher import enrich_skill_metadata


def test_enrich_skill_metadata__matching_experiences__sums_years() -> None:
    experiences = [
        ExperienceItem(
            company="Acme",
            role="Engineer",
            start_date=date(2020, 1, 1),
            end_date=date(2021, 1, 1),
            description="Built Python services",
            is_current=False,
        ),
        ExperienceItem(
            company="Beta",
            role="Engineer",
            start_date=date(2021, 2, 1),
            end_date=date(2022, 2, 1),
            description="Python data pipelines",
            is_current=False,
        ),
    ]

    result = enrich_skill_metadata("python", experiences, certifications=[])

    assert result["years"] == pytest.approx(2.0, rel=0.01)
    assert result["level"] == "intermediate"


def test_enrich_skill_metadata__no_matches__returns_zero_years() -> None:
    experiences = [
        ExperienceItem(
            company="Acme",
            role="Engineer",
            start_date=date(2020, 1, 1),
            end_date=date(2021, 1, 1),
            description="Built Java services",
            is_current=False,
        )
    ]

    result = enrich_skill_metadata("python", experiences, certifications=[])

    assert result["years"] == 0.0
    assert result["level"] == "junior"
    assert result["certified"] is False


def test_enrich_skill_metadata__certification_substring_match__sets_certified() -> None:
    experiences: list[ExperienceItem] = []
    certifications = ["AWS Solutions Architect"]

    result = enrich_skill_metadata("aws", experiences, certifications)

    assert result["certified"] is True


def test_enrich_skill_metadata__fuzzy_certification_match__sets_certified() -> None:
    experiences: list[ExperienceItem] = []
    certifications = ["Kubernetess Administrator"]

    result = enrich_skill_metadata("kubernetes", experiences, certifications)

    assert result["certified"] is True


def test_enrich_skill_metadata__years_over_ten__sets_expert_level() -> None:
    experiences = [
        ExperienceItem(
            company="Acme",
            role="Engineer",
            start_date=date(2010, 1, 1),
            end_date=date(2021, 1, 1),
            description="Python backend development",
            is_current=False,
        )
    ]

    result = enrich_skill_metadata("python", experiences, certifications=[])

    assert result["years"] == pytest.approx(11.0, rel=0.01)
    assert result["level"] == "expert"
