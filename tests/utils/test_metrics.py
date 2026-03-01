"""Tests for ingestion metrics (uses fakeredis)."""

from __future__ import annotations

import pytest

from src.utils.metrics import IngestionMetrics, MetricSnapshot, track_ingestion

# ---------------------------------------------------------------------------
# We use fakeredis to avoid needing a real Redis instance.
# If fakeredis is not installed, tests are skipped.
# ---------------------------------------------------------------------------
fakeredis = pytest.importorskip("fakeredis")


@pytest.fixture()
def redis_client():
    """Create a fakeredis client for testing."""
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture()
def metrics(redis_client) -> IngestionMetrics:
    return IngestionMetrics(redis_client=redis_client)


def test_record_success__increments_counters(metrics: IngestionMetrics) -> None:
    metrics.record_success("docx_cv", latency_ms=150.0)
    snap = metrics.get_snapshot("docx_cv")

    assert snap.success_count == 1
    assert snap.failure_count == 0
    assert snap.total_count == 1
    assert snap.avg_latency_ms == pytest.approx(150.0)
    assert snap.last_success_ts is not None
    assert snap.last_failure_ts is None


def test_record_failure__increments_counters(metrics: IngestionMetrics) -> None:
    metrics.record_failure("docx_cv", latency_ms=50.0)
    snap = metrics.get_snapshot("docx_cv")

    assert snap.success_count == 0
    assert snap.failure_count == 1
    assert snap.total_count == 1
    assert snap.last_failure_ts is not None


def test_multiple_records__avg_latency(metrics: IngestionMetrics) -> None:
    metrics.record_success("reskilling_api", latency_ms=100.0)
    metrics.record_success("reskilling_api", latency_ms=200.0)
    snap = metrics.get_snapshot("reskilling_api")

    assert snap.success_count == 2
    assert snap.total_count == 2
    assert snap.avg_latency_ms == pytest.approx(150.0)


def test_get_snapshot__empty__returns_zeros(metrics: IngestionMetrics) -> None:
    snap = metrics.get_snapshot("nonexistent")
    assert snap.success_count == 0
    assert snap.failure_count == 0
    assert snap.total_count == 0
    assert snap.avg_latency_ms == 0.0


def test_get_all_snapshots__multiple_sources(metrics: IngestionMetrics) -> None:
    metrics.record_success("docx_cv", latency_ms=10.0)
    metrics.record_failure("reskilling_api", latency_ms=20.0)
    snapshots = metrics.get_all_snapshots()

    source_types = {s.source_type for s in snapshots}
    assert "docx_cv" in source_types
    assert "reskilling_api" in source_types


def test_reset__clears_all_counters(metrics: IngestionMetrics) -> None:
    metrics.record_success("docx_cv", latency_ms=100.0)
    metrics.record_failure("docx_cv", latency_ms=50.0)
    metrics.reset("docx_cv")

    snap = metrics.get_snapshot("docx_cv")
    assert snap.total_count == 0
    assert snap.success_count == 0
    assert snap.failure_count == 0


def test_track_ingestion_decorator__success(redis_client) -> None:
    test_metrics = IngestionMetrics(redis_client=redis_client)

    @track_ingestion("test_source", metrics=test_metrics)
    def my_task() -> str:
        return "ok"

    result = my_task()
    assert result == "ok"

    snap = test_metrics.get_snapshot("test_source")
    assert snap.success_count == 1
    assert snap.failure_count == 0


def test_track_ingestion_decorator__failure(redis_client) -> None:
    test_metrics = IngestionMetrics(redis_client=redis_client)

    @track_ingestion("test_source", metrics=test_metrics)
    def my_failing_task() -> str:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        my_failing_task()

    snap = test_metrics.get_snapshot("test_source")
    assert snap.success_count == 0
    assert snap.failure_count == 1


def test_metric_snapshot__dataclass_fields() -> None:
    snap = MetricSnapshot(
        source_type="test",
        success_count=5,
        failure_count=2,
        total_count=7,
        avg_latency_ms=120.5,
    )
    assert snap.source_type == "test"
    assert snap.total_count == 7
    assert snap.last_success_ts is None
