"""Ingestion status service for res_id queries."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import redis

from src.core.config import get_settings
from src.services.embedding.freshness import FreshnessGate
from src.services.ingestion.status_schemas import IngestionStatusResponse

logger = logging.getLogger(__name__)

PIPELINE_LAST_RUN_AT_KEY = "pipeline:last_run_at"


class RedisClient(Protocol):
    def get(self, key: str) -> str | None: ...


class FreshnessGateProtocol(Protocol):
    def is_fresh(self, res_id: int) -> bool: ...


class IngestionStatusError(RuntimeError):
    """Raised when ingestion status cannot be computed."""


@dataclass(frozen=True)
class IngestionStatusService:
    """Service that returns ingestion freshness and staleness info."""

    redis_client: RedisClient | None = None
    freshness_gate: FreshnessGateProtocol | None = None

    def __post_init__(self) -> None:
        settings = get_settings()
        if self.redis_client is None:
            try:
                client = redis.from_url(settings.celery_result_backend, decode_responses=True)
            except (redis.RedisError, ValueError) as exc:
                logger.warning("Redis client initialization failed: %s", exc)
                client = None
            object.__setattr__(self, "redis_client", client)
        if self.freshness_gate is None:
            object.__setattr__(self, "freshness_gate", FreshnessGate())

    def get_status(self, res_id: int) -> IngestionStatusResponse:
        """Return ingestion status data for a given res_id.

        Args:
            res_id: Resource identifier.

        Returns:
            IngestionStatusResponse containing freshness and staleness details.

        Raises:
            ValueError: When res_id is invalid.
            IngestionStatusError: When Redis is unavailable or data is invalid.
        """
        if not res_id or res_id <= 0:
            raise ValueError("res_id must be a positive integer")

        client = self.redis_client
        if client is None:
            raise IngestionStatusError("Redis unavailable for ingestion status")

        gate = self.freshness_gate
        if gate is None:
            raise IngestionStatusError("Freshness gate unavailable")

        last_ingested_at = self._load_last_ingested_at(client)
        is_fresh = gate.is_fresh(res_id)
        staleness_seconds = _calc_staleness_seconds(last_ingested_at)

        return IngestionStatusResponse(
            res_id=res_id,
            last_ingested_at=last_ingested_at,
            is_fresh=is_fresh,
            staleness_seconds=staleness_seconds,
        )

    def _load_last_ingested_at(self, client: RedisClient) -> datetime | None:
        try:
            raw = client.get(PIPELINE_LAST_RUN_AT_KEY)
        except redis.RedisError as exc:
            logger.warning("Failed to read ingestion status from Redis: %s", exc)
            raise IngestionStatusError("Redis unavailable for ingestion status") from exc

        if not raw:
            return None

        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError as exc:
            logger.warning("Invalid ingestion status timestamp: %s", raw)
            raise IngestionStatusError("Invalid ingestion status timestamp") from exc

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed


def _calc_staleness_seconds(last_ingested_at: datetime | None) -> int | None:
    if last_ingested_at is None:
        return None
    now = datetime.now(UTC)
    return max(0, int((now - last_ingested_at).total_seconds()))


__all__ = ["IngestionStatusError", "IngestionStatusService"]
