"""API endpoint for pipeline status checks."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from src.services.pipeline.schemas import PipelineStatusResponse
from src.services.pipeline.status_service import PipelineStatusService

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])

TOTAL_SOURCES = 3


@router.get(
    "/status",
    response_model=PipelineStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Stato avanzamento pipeline",
)
def get_pipeline_status() -> PipelineStatusResponse:
    """Return the ingestion pipeline status from live sources."""
    service = PipelineStatusService()
    result = service.get_status()
    if result.failed_sources >= TOTAL_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tutti i servizi della pipeline sono irraggiungibili",
        )
    return result.response
