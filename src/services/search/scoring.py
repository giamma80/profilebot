"""Scoring helpers for skill-based search results."""

from __future__ import annotations

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
    normalized_weights = (weights or ScoreWeights()).normalized()
    match_ratio = calculate_match_ratio(matched, query)
    similarity_clamped = min(1.0, max(0.0, similarity))
    final_score = (
        similarity_clamped * normalized_weights.similarity
        + match_ratio * normalized_weights.match_ratio
    )
    return min(1.0, max(0.0, final_score))
