"""Fusion helpers for combining search results across layers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, TypeVar


class ScoredCandidate(Protocol):
    cv_id: str
    score: float


T = TypeVar("T", bound=ScoredCandidate)


def rrf_fuse(
    primary: Sequence[T],
    secondary: Sequence[T],
    *,
    k: int = 60,
) -> list[T]:
    """Fuse results using Reciprocal Rank Fusion.

    Args:
        primary: Primary ranked candidates.
        secondary: Secondary ranked candidates.
        k: RRF constant controlling decay.

    Returns:
        Fused list of candidates sorted by RRF score.
    """
    scores: dict[str, float] = {}
    items: dict[str, T] = {}

    for ranked in (primary, secondary):
        for rank, item in enumerate(ranked, start=1):
            scores[item.cv_id] = scores.get(item.cv_id, 0.0) + 1.0 / (k + rank)
            items.setdefault(item.cv_id, item)

    return sorted(items.values(), key=lambda candidate: scores[candidate.cv_id], reverse=True)


def weighted_fuse(
    primary: Sequence[T],
    secondary: Sequence[T],
    *,
    weight_primary: float = 0.7,
    weight_secondary: float = 0.3,
) -> list[T]:
    """Fuse results using weighted score combination.

    Args:
        primary: Primary candidates with scores.
        secondary: Secondary candidates with scores.
        weight_primary: Weight applied to primary scores.
        weight_secondary: Weight applied to secondary scores.

    Returns:
        Fused list of candidates sorted by weighted score.
    """
    total_weight = weight_primary + weight_secondary
    if total_weight <= 0:
        return list(primary)

    w_primary = weight_primary / total_weight
    w_secondary = weight_secondary / total_weight

    primary_scores = {item.cv_id: item.score for item in primary}
    secondary_scores = {item.cv_id: item.score for item in secondary}
    items: dict[str, T] = {item.cv_id: item for item in secondary}
    items.update({item.cv_id: item for item in primary})

    def fused_score(candidate: T) -> float:
        return (primary_scores.get(candidate.cv_id, 0.0) * w_primary) + (
            secondary_scores.get(candidate.cv_id, 0.0) * w_secondary
        )

    return sorted(items.values(), key=fused_score, reverse=True)
