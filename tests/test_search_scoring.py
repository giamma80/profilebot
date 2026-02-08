from __future__ import annotations

import pytest

from src.services.search.scoring import ScoreWeights, calculate_final_score, calculate_match_ratio


def test_calculate_match_ratio__matches_subset__returns_expected_ratio() -> None:
    # Arrange
    matched = {"python", "fastapi"}
    query = {"python", "fastapi", "postgresql"}

    # Act
    ratio = calculate_match_ratio(matched, query)

    # Assert
    assert ratio == pytest.approx(2 / 3)


def test_calculate_final_score__default_weights__combines_similarity_and_match_ratio() -> None:
    # Arrange
    similarity = 0.9
    matched = {"python", "fastapi"}
    query = {"python", "fastapi", "postgresql"}

    # Act
    score = calculate_final_score(similarity, matched, query)

    # Assert
    expected = (0.9 * 0.7) + ((2 / 3) * 0.3)
    assert score == pytest.approx(expected)


def test_calculate_final_score__custom_weights__normalize_to_sum_one() -> None:
    # Arrange
    similarity = 0.5
    matched = {"python"}
    query = {"python", "fastapi"}
    weights = ScoreWeights(similarity=2.0, match_ratio=1.0)

    # Act
    score = calculate_final_score(similarity, matched, query, weights=weights)

    # Assert
    expected = (0.5 * (2 / 3)) + ((1 / 2) * (1 / 3))
    assert score == pytest.approx(expected)


def test_calculate_final_score__out_of_range_similarity__clamps_score() -> None:
    # Arrange
    similarity = 1.5
    matched = {"python"}
    query = {"python"}

    # Act
    score = calculate_final_score(similarity, matched, query)

    # Assert
    assert score == pytest.approx(1.0)


def test_calculate_final_score__empty_query__returns_zero_match_ratio() -> None:
    # Arrange
    similarity = 0.4
    matched: set[str] = set()
    query: set[str] = set()

    # Act
    score = calculate_final_score(similarity, matched, query)

    # Assert
    expected = 0.4 * 0.7
    assert score == pytest.approx(expected)
