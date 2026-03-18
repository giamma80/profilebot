"""Redis helper utilities for ProfileBot."""

from __future__ import annotations

import logging

import redis

from src.core.config import get_settings

logger = logging.getLogger(__name__)


def build_docx_redis_client() -> redis.Redis | None:
    """Build a Redis client for the DOCX cache.

    Returns:
        Redis client when available, otherwise None.
    """
    settings = get_settings()
    try:
        client = redis.from_url(settings.redis_url, decode_responses=False)
        client.ping()
        return client
    except (redis.RedisError, ValueError) as exc:
        logger.warning("docx.cache_redis_unavailable: %s", exc)
        return None
