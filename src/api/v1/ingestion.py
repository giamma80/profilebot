"""API endpoints for profile ingestion."""

from __future__ import annotations

import logging
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.core.config import get_settings
from src.services.ingestion.profile_service import ProfileIngestionService

logger = logging.getLogger(__name__)

SERVER_ERROR_STATUS_CODE = 500

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])


class IngestionResponse(BaseModel):
    """Response payload for single res_id ingestion."""

    status: Literal["success", "skipped"]
    res_id: int
    cv_id: str | None = None
    totals: dict[str, int] | None = None
    availability_cached: bool = False
    reskilling_cached: bool = False
    reason: str | None = None

    model_config = {"extra": "forbid"}


@router.post(
    "/res-id/{res_id}",
    response_model=IngestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest profile by res_id",
)
async def ingest_res_id(res_id: int, force: bool = False) -> IngestionResponse:
    """Ingest a single profile end-to-end by res_id."""
    settings = get_settings()
    if not settings.scraper_base_url.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SCRAPER_BASE_URL not configured",
        )

    service = ProfileIngestionService()
    try:
        outcome = service.ingest_res_id(res_id, force=force)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.RequestError as exc:
        logger.warning("Ingestion scraper request failed for res_id %s: %s", res_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scraper unavailable",
        ) from exc
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        logger.warning("Ingestion scraper HTTP error for res_id %s: %s", res_id, exc)
        if status_code is not None and status_code >= SERVER_ERROR_STATUS_CODE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Scraper unavailable",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Scraper error",
        ) from exc
    except Exception as exc:
        logger.exception("Ingestion failed for res_id %s", res_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ingestion failed",
        ) from exc

    return IngestionResponse(
        status=outcome.status,
        res_id=outcome.res_id,
        cv_id=outcome.cv_id,
        totals=outcome.totals,
        availability_cached=outcome.availability_cached,
        reskilling_cached=outcome.reskilling_cached,
        reason=outcome.reason,
    )
