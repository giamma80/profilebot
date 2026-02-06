"""Qdrant health check helper."""

from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient


def check_qdrant_health(client: QdrantClient) -> dict[str, Any]:
    """
    Perform a basic health check against Qdrant.

    Returns a dict with status and optional error details.
    Raises exceptions from the client if Qdrant is unreachable.
    """
    # The Qdrant client exposes get_collections() as a lightweight call.
    collections = client.get_collections()
    return {
        "status": "ok",
        "collections_count": len(collections.collections),
    }
