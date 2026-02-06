"""Tests for Qdrant connectivity."""

from __future__ import annotations

from src.services.qdrant import get_qdrant_client


def test_qdrant_connection() -> None:
    """Fail if Qdrant is not reachable."""
    client = get_qdrant_client()
    collections = client.get_collections()
    assert collections is not None
