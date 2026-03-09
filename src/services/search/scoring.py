"""Scoring helpers for skill-based search results."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreWeights:
    """Weights used to combine similarity and match ratio."""

    similarity: float = 0.7
    match_ratio: float = 0.3

    def normalized(self) -> ScoreWeights:
        """Return weights normalized to sum to 1.0."""
        total = self.similarity + self.match_ratio
        if total <= 0:
            return ScoreWeights()
        return ScoreWeights(self.similarity / total, self.match_ratio / total)


def calculate_match_ratio(matched: set[str], query: set[str]) -> float:
    """Calculate match ratio between matched skills and query skills.

    Args:
        matched: Set of matched skill identifiers.
        query: Set of requested skill identifiers.

    Returns:
        Ratio in the range 0.0 - 1.0.
    """
    if not query:
        return 0.0
    return min(1.0, max(0.0, len(matched) / len(query)))


def calculate_weighted_match_ratio(
    matched: set[str],
    query: list[str],
    weight_map: Mapping[str, float],
    *,
    default_weight: float = 1.0,
) -> float:
    """Calculate weighted match ratio for a query.

    Args:
        matched: Set of matched skill identifiers.
        query: Ordered list of requested skills.
        weight_map: Mapping from skill name to weight.
        default_weight: Weight applied when missing from the map.

    Returns:
        Weighted match ratio in the range 0.0 - 1.0.
    """
    if not query:
        return 0.0

    total_weight = 0.0
    matched_weight = 0.0
    for skill in query:
        weight = weight_map.get(skill, default_weight)
        weight = max(0.0, weight)
        total_weight += weight
        if skill in matched:
            matched_weight += weight

    if total_weight <= 0:
        return 0.0
    ratio = matched_weight / total_weight
    return min(1.0, max(0.0, ratio))


def calculate_skill_score(
    similarity: float,
    weighted_match_ratio: float,
    *,
    weights: ScoreWeights | None = None,
) -> float:
    """Combine similarity and weighted match ratio into a skill score.

    Args:
        similarity: Cosine similarity from vector search (0.0 - 1.0).
        weighted_match_ratio: Weighted match ratio for the query.
        weights: Optional weighting configuration.

    Returns:
        Skill score in the range 0.0 - 1.0.
    """
    normalized_weights = (weights or ScoreWeights()).normalized()
    similarity_clamped = min(1.0, max(0.0, similarity))
    ratio_clamped = min(1.0, max(0.0, weighted_match_ratio))
    final_score = (
        similarity_clamped * normalized_weights.similarity
        + ratio_clamped * normalized_weights.match_ratio
    )
    return min(1.0, max(0.0, final_score))


def calculate_weighted_final_score(
    similarity: float,
    weighted_match_ratio: float,
    domain_boost: float,
    seniority_penalty: float,
    *,
    weight_skill: float = 1.0,
) -> float:
    """Combine weighted skill score with domain boost and seniority penalty.

    Args:
        similarity: Cosine similarity from vector search (0.0 - 1.0).
        weighted_match_ratio: Weighted match ratio for the query.
        domain_boost: Domain boost applied when domain matches.
        seniority_penalty: Penalty based on seniority mismatch.
        weight_skill: Weight applied to the weighted skill score.

    Returns:
        Final score in the range 0.0 - 1.0.
    """
    skill_score = calculate_skill_score(similarity, weighted_match_ratio)
    final_score = (skill_score * weight_skill) + domain_boost - seniority_penalty
    return min(1.0, max(0.0, final_score))


def calculate_final_score(
    similarity: float,
    matched: set[str],
    query: set[str],
    *,
    weights: ScoreWeights | None = None,
) -> float:
    """Combine similarity and match ratio into a final score.

    Args:
        similarity: Cosine similarity from vector search (0.0 - 1.0).
        matched: Set of matched skill identifiers.
        query: Set of requested skill identifiers.
        weights: Optional weighting configuration.

    Returns:
        Final score in the range 0.0 - 1.0.
    """
    match_ratio = calculate_match_ratio(matched, query)
    return calculate_skill_score(similarity, match_ratio, weights=weights)


__all__ = [
    "ScoreWeights",
    "calculate_final_score",
    "calculate_match_ratio",
    "calculate_skill_score",
    "calculate_weighted_final_score",
    "calculate_weighted_match_ratio",
]
