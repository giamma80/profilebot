"""Qdrant client factory."""

from __future__ import annotations

import os
from functools import lru_cache

from qdrant_client import QdrantClient


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    """Return a cached Qdrant client instance."""
    url = _get_env("QDRANT_URL", "http://localhost:6333")
    api_key = _get_env("QDRANT_API_KEY")
    timeout = float(_get_env("QDRANT_TIMEOUT", "10"))

    # QdrantClient accepts `url` for HTTP and optional `api_key`.
    return QdrantClient(url=url, api_key=api_key, timeout=timeout)
