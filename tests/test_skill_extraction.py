from __future__ import annotations

import logging
from pathlib import Path

import pytest

from src.core.parser.schemas import CVMetadata, ParsedCV, SkillSection
from src.core.skills.dictionary import load_skill_dictionary
from src.core.skills.extractor import SkillExtractor
from src.core.skills.normalizer import FUZZY_THRESHOLD, SkillNormalizer


@pytest.fixture()
def dictionary():
    return load_skill_dictionary(Path("data/skills_dictionary.yaml"))


@pytest.fixture()
def normalizer(dictionary):
    return SkillNormalizer(dictionary)


@pytest.fixture()
def extractor(dictionary):
    return SkillExtractor(dictionary)


def test_normalize_skill__exact_match__returns_confidence_1(normalizer):
    # Act
    result = normalizer.normalize("Python")

    # Assert
    assert result is not None
    assert result.canonical == "python"
    assert result.confidence == 1.0
    assert result.match_type == "exact"


def test_normalize_skill__alias_match__returns_confidence_095(normalizer):
    # Act
    result = normalizer.normalize("py")

    # Assert
    assert result is not None
    assert result.canonical == "python"
    assert result.confidence == 0.95
    assert result.match_type == "alias"


def test_normalize_skill__fuzzy_match__returns_ratio_based_confidence(normalizer):
    # Act
    result = normalizer.normalize("pythn")

    # Assert
    assert result is not None
    assert result.canonical == "python"
    assert result.match_type == "fuzzy"
    assert result.confidence >= FUZZY_THRESHOLD / 100


def test_normalize_skill__case_insensitive__returns_canonical(normalizer):
    # Act
    result = normalizer.normalize("PYTHON")

    # Assert
    assert result is not None
    assert result.canonical == "python"


def test_normalize_skill__unknown__returns_none(normalizer):
    # Act
    result = normalizer.normalize("xyz123")

    # Assert
    assert result is None


def test_normalize_skill__empty_string__returns_none(normalizer):
    # Act
    result = normalizer.normalize("   ")

    # Assert
    assert result is None


def test_extract_skills__logs_unknown_and_collects_results(extractor, caplog):
    # Arrange
    caplog.set_level(logging.WARNING)
    raw_skills = ["Python", "py", "Pythn", "xyz123", ""]

    # Act
    result = extractor.extract_from_raw(cv_id="cv-test", raw_skills=raw_skills)

    # Assert
    assert len(result.normalized_skills) == 3
    assert result.unknown_skills == ["xyz123"]
    assert "Unknown skill" in caplog.text


def test_extract_skills__stats_percentages_are_consistent(extractor):
    # Arrange
    raw_skills = ["Python", "py", "Pythn", "xyz123"]

    # Act
    result = extractor.extract_from_raw(cv_id="cv-stats", raw_skills=raw_skills)
    stats = result.get_stats()

    # Assert
    assert stats["exact_pct"] == pytest.approx(25.0)
    assert stats["alias_pct"] == pytest.approx(25.0)
    assert stats["fuzzy_pct"] == pytest.approx(25.0)
    assert stats["unknown_pct"] == pytest.approx(25.0)


def test_extract_from_parsed_cv__uses_skill_keywords_when_available(extractor):
    # Arrange
    metadata = CVMetadata(cv_id="cv-1", file_name="cv.docx")
    skills = SkillSection(raw_text="Python, FastAPI", skill_keywords=["Python", "FastAPI"])
    parsed = ParsedCV(
        metadata=metadata,
        skills=skills,
        experiences=[],
        education=[],
        certifications=[],
        raw_text="",
    )

    # Act
    result = extractor.extract_from_parsed_cv(parsed)

    # Assert
    canonical = {skill.canonical for skill in result.normalized_skills}
    assert canonical == {"python", "fastapi"}


def test_extract_from_parsed_cv__falls_back_to_raw_text_when_missing_keywords(extractor):
    # Arrange
    metadata = CVMetadata(cv_id="cv-2", file_name="cv.docx")
    skills = SkillSection(raw_text="Python, FastAPI", skill_keywords=[])
    parsed = ParsedCV(
        metadata=metadata,
        skills=skills,
        experiences=[],
        education=[],
        certifications=[],
        raw_text="",
    )

    # Act
    result = extractor.extract_from_parsed_cv(parsed)

    # Assert
    canonical = {skill.canonical for skill in result.normalized_skills}
    assert canonical == {"python", "fastapi"}


def test_dictionary__contains_minimum_entries(dictionary):
    # Assert
    assert dictionary.canonical_count >= 100
