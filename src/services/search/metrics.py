"""Prometheus counters for search pipeline metrics."""

from __future__ import annotations

from prometheus_client import Counter

FALLBACK_ACTIVATED = Counter(
    "search_fallback_activated_total",
    "Fallback activations in skill search",
)
CHUNK_RESULTS = Counter(
    "search_chunk_results_count",
    "Chunk search results returned",
)
FUSION_USED = Counter(
    "search_fusion_used_total",
    "Fusion strategy activations",
)

__all__ = ["CHUNK_RESULTS", "FALLBACK_ACTIVATED", "FUSION_USED"]
