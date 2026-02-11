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
    timeout_raw = _get_env("QDRANT_TIMEOUT", "10")
    timeout = int(timeout_raw) if timeout_raw is not None else None

    if url is None:
        url = "http://localhost:6333"

    api_key_to_use = api_key if url.startswith("https://") else None

    # QdrantClient accepts `url` for HTTP and optional `api_key`.
    return QdrantClient(url=url, api_key=api_key_to_use, timeout=timeout)
