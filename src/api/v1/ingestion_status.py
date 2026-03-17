"""API endpoint for ingestion status checks."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from src.services.ingestion.status_schemas import IngestionStatusResponse
from src.services.ingestion.status_service import (
    IngestionStatusError,
    IngestionStatusService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])


@router.get(
    "/status/{res_id}",
    response_model=IngestionStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Stato ingestion per res_id",
)
def get_ingestion_status(res_id: int) -> IngestionStatusResponse:
    """Return ingestion status for the requested res_id.

    Args:
        res_id: Resource identifier.

    Returns:
        IngestionStatusResponse with last ingestion and freshness info.
        Note: last_ingested_at reflects the last pipeline run, not the specific res_id.

    Raises:
        HTTPException: For invalid input or unavailable backend.
    """
    service = IngestionStatusService()
    try:
        return service.get_status(res_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IngestionStatusError as exc:
        logger.warning("Ingestion status unavailable for res_id %s: %s", res_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestion status unavailable",
        ) from exc
