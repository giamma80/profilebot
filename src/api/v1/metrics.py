"""Ingestion metrics API endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.utils.metrics import IngestionMetrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


class MetricSnapshotResponse(BaseModel):
    """Response model for a single source_type metric snapshot."""

    source_type: str
    success_count: int
    failure_count: int
    total_count: int
    avg_latency_ms: float
    last_success_ts: float | None
    last_failure_ts: float | None


class IngestionMetricsResponse(BaseModel):
    """Response for the ingestion metrics endpoint."""

    metrics: list[MetricSnapshotResponse]


@router.get("/ingestion", response_model=IngestionMetricsResponse)
def get_ingestion_metrics() -> IngestionMetricsResponse:
    """Return aggregated ingestion metrics for all source types."""
    try:
        tracker = IngestionMetrics()
        snapshots = tracker.get_all_snapshots()
    except Exception as exc:
        logger.warning("Failed to retrieve ingestion metrics: %s", exc)
        raise HTTPException(status_code=503, detail="Metrics unavailable") from exc

    return IngestionMetricsResponse(
        metrics=[
            MetricSnapshotResponse(
                source_type=s.source_type,
                success_count=s.success_count,
                failure_count=s.failure_count,
                total_count=s.total_count,
                avg_latency_ms=s.avg_latency_ms,
                last_success_ts=s.last_success_ts,
                last_failure_ts=s.last_failure_ts,
            )
            for s in snapshots
        ]
    )
