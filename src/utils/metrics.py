"""Ingestion metrics — Redis-backed counters per source_type."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import ParamSpec, TypeVar

import redis
from prometheus_client import CollectorRegistry, Counter
from prometheus_client.core import GaugeMetricFamily

from src.core.config import get_settings

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")

METRICS_KEY_PREFIX = "profilebot:metrics:ingestion"

CHORD_PARTIAL_FAILURES = Counter(
    "profilebot_chord_partial_failures_total",
    "Total partial failures in best-effort chords",
)


@dataclass(frozen=True)
class MetricSnapshot:
    """Point-in-time snapshot of metrics for a source_type."""

    source_type: str
    success_count: int = 0
    failure_count: int = 0
    total_count: int = 0
    last_success_ts: float | None = None
    last_failure_ts: float | None = None
    avg_latency_ms: float = 0.0


class IngestionMetrics:
    """Redis-backed ingestion metrics tracker.

    Stores per-source counters:
        - ``{prefix}:{source_type}:success``   — success count
        - ``{prefix}:{source_type}:failure``   — failure count
        - ``{prefix}:{source_type}:total``     — total invocations
        - ``{prefix}:{source_type}:latency_sum`` — cumulative latency (ms)
        - ``{prefix}:{source_type}:last_success`` — timestamp of last success
        - ``{prefix}:{source_type}:last_failure`` — timestamp of last failure
    """

    def __init__(self, redis_client: redis.Redis | None = None) -> None:
        if redis_client is not None:
            self._redis = redis_client
        else:
            settings = get_settings()
            self._redis = redis.from_url(settings.redis_url, decode_responses=True)

    def _key(self, source_type: str, metric: str) -> str:
        return f"{METRICS_KEY_PREFIX}:{source_type}:{metric}"

    def record_success(self, source_type: str, latency_ms: float) -> None:
        """Record a successful ingestion."""

        pipe = self._redis.pipeline(transaction=False)
        pipe.incr(self._key(source_type, "success"))
        pipe.incr(self._key(source_type, "total"))
        pipe.incrbyfloat(self._key(source_type, "latency_sum"), latency_ms)
        pipe.set(self._key(source_type, "last_success"), str(time.time()))
        pipe.execute()

    def record_failure(self, source_type: str, latency_ms: float) -> None:
        """Record a failed ingestion."""

        pipe = self._redis.pipeline(transaction=False)
        pipe.incr(self._key(source_type, "failure"))
        pipe.incr(self._key(source_type, "total"))
        pipe.incrbyfloat(self._key(source_type, "latency_sum"), latency_ms)
        pipe.set(self._key(source_type, "last_failure"), str(time.time()))
        pipe.execute()

    def get_snapshot(self, source_type: str) -> MetricSnapshot:
        """Retrieve current metrics for a source_type."""
        pipe = self._redis.pipeline(transaction=False)
        pipe.get(self._key(source_type, "success"))
        pipe.get(self._key(source_type, "failure"))
        pipe.get(self._key(source_type, "total"))
        pipe.get(self._key(source_type, "latency_sum"))
        pipe.get(self._key(source_type, "last_success"))
        pipe.get(self._key(source_type, "last_failure"))
        results = pipe.execute()

        success = int(results[0] or 0)
        failure = int(results[1] or 0)
        total = int(results[2] or 0)
        latency_sum = float(results[3] or 0.0)
        last_success = float(results[4]) if results[4] else None
        last_failure = float(results[5]) if results[5] else None

        avg_latency = latency_sum / total if total > 0 else 0.0

        return MetricSnapshot(
            source_type=source_type,
            success_count=success,
            failure_count=failure,
            total_count=total,
            last_success_ts=last_success,
            last_failure_ts=last_failure,
            avg_latency_ms=avg_latency,
        )

    def get_all_snapshots(self) -> list[MetricSnapshot]:
        """Retrieve metrics for all known source types."""
        pattern = f"{METRICS_KEY_PREFIX}:*:total"
        keys = list(self._redis.scan_iter(match=pattern))
        source_types: set[str] = set()
        for key in keys:
            # key format: profilebot:metrics:ingestion:{source_type}:total
            parts = key.split(":")
            _source_type_idx = 3
            if len(parts) > _source_type_idx:
                source_types.add(parts[_source_type_idx])
        return [self.get_snapshot(st) for st in sorted(source_types)]

    def reset(self, source_type: str) -> None:
        """Reset all metrics for a source_type."""
        suffixes = ["success", "failure", "total", "latency_sum", "last_success", "last_failure"]
        keys = [self._key(source_type, s) for s in suffixes]
        self._redis.delete(*keys)


class RedisMetricsCollector:
    """Prometheus Custom Collector to scrape metrics from Redis directly."""

    def __init__(self) -> None:
        self.metrics = IngestionMetrics()

    def collect(self) -> list:
        snapshots = self.metrics.get_all_snapshots()

        total_processed = GaugeMetricFamily(
            "profilebot_profiles_processed_total",
            "Total number of profiles processed",
            labels=["source_type", "status"],
        )
        avg_latency = GaugeMetricFamily(
            "profilebot_profiles_avg_latency_ms",
            "Average latency in MS processing a profile",
            labels=["source_type"],
        )

        for s in snapshots:
            total_processed.add_metric([s.source_type, "success"], s.success_count)
            total_processed.add_metric([s.source_type, "error"], s.failure_count)
            avg_latency.add_metric([s.source_type], s.avg_latency_ms)

        return [total_processed, avg_latency]


def get_metrics_registry() -> CollectorRegistry:
    """Return a custom CollectorRegistry exposing our Redis-backed metrics."""
    registry = CollectorRegistry()
    registry.register(RedisMetricsCollector())
    return registry


def track_ingestion(
    source_type: str,
    metrics: IngestionMetrics | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to track ingestion metrics on a function.

    Usage::

        @track_ingestion("docx_cv")
        def ingest_cv(file_path: str) -> dict:
            ...

    Works with both regular functions and Celery tasks.
    """

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            _metrics = metrics
            if _metrics is None:
                try:
                    _metrics = IngestionMetrics()
                except Exception:
                    logger.warning("metrics_init_failed for %s, skipping tracking", source_type)
                    return fn(*args, **kwargs)

            start = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                latency = (time.perf_counter() - start) * 1000
                try:
                    _metrics.record_success(source_type, latency)
                except Exception:
                    logger.warning("metrics_record_failed for %s", source_type)
                return result
            except Exception:
                latency = (time.perf_counter() - start) * 1000
                try:
                    _metrics.record_failure(source_type, latency)
                except Exception:
                    logger.warning("metrics_record_failed for %s", source_type)
                raise

        return wrapper

    return decorator


__all__ = [
    "CHORD_PARTIAL_FAILURES",
    "IngestionMetrics",
    "MetricSnapshot",
    "get_metrics_registry",
    "track_ingestion",
]
