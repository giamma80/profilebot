"""API endpoints for availability cache management."""

from __future__ import annotations

import io
import logging
from datetime import datetime

import redis
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, model_validator

from src.services.availability.cache import AvailabilityCache
from src.services.availability.loader import load_from_csv, load_from_stream
from src.services.availability.schemas import AvailabilityStatus
from src.services.availability.service import AvailabilityService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/availability", tags=["availability"])


class AvailabilityLoadRequest(BaseModel):
    """Request payload for loading availability data."""

    csv_path: str | None = None
    csv_content: str | None = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def validate_payload(self) -> AvailabilityLoadRequest:
        if not self.csv_path and not self.csv_content:
            raise ValueError("Either csv_path or csv_content is required")
        return self


class AvailabilityLoadResponse(BaseModel):
    """Response payload for a load operation."""

    total_rows: int
    loaded: int
    skipped: int


class AvailabilityResponse(BaseModel):
    """Response payload for a single availability record."""

    res_id: int
    status: AvailabilityStatus
    allocation_pct: int
    current_project: str | None = None
    available_from: str | None = None
    available_to: str | None = None
    manager_name: str | None = None
    updated_at: str


class AvailabilityStatsResponse(BaseModel):
    """Response payload with availability cache stats."""

    total: int
    by_status: dict[AvailabilityStatus, int]
    last_updated_at: str | None = None


@router.post(
    "/load",
    response_model=AvailabilityLoadResponse,
    status_code=status.HTTP_200_OK,
    summary="Carica disponibilità da CSV",
)
def load_availability(request: AvailabilityLoadRequest) -> AvailabilityLoadResponse:
    """Load availability data into Redis cache from CSV path or body."""
    try:
        if request.csv_path:
            result = load_from_csv(request.csv_path)
        else:
            stream = io.StringIO(request.csv_content or "")
            result = load_from_stream(stream)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except redis.RedisError as exc:
        logger.warning("Redis error during availability load: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis unavailable",
        ) from exc

    return AvailabilityLoadResponse(
        total_rows=result.total_rows,
        loaded=result.loaded,
        skipped=result.skipped,
    )


@router.get(
    "/{res_id}",
    response_model=AvailabilityResponse,
    status_code=status.HTTP_200_OK,
    summary="Ottieni disponibilità per res_id",
)
def get_availability(res_id: int) -> AvailabilityResponse:
    """Return availability record for a given res_id from cache."""
    service = AvailabilityService()
    record = service.get_availability(res_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="res_id not found")

    return AvailabilityResponse(
        res_id=record.res_id,
        status=record.status,
        allocation_pct=record.allocation_pct,
        current_project=record.current_project,
        available_from=record.available_from.isoformat() if record.available_from else None,
        available_to=record.available_to.isoformat() if record.available_to else None,
        manager_name=record.manager_name,
        updated_at=record.updated_at.isoformat(),
    )


@router.get(
    "/stats",
    response_model=AvailabilityStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Statistiche disponibilità cache",
)
def get_availability_stats() -> AvailabilityStatsResponse:
    """Return availability cache statistics."""
    cache = AvailabilityCache()
    try:
        records = cache.scan_records()
    except redis.RedisError as exc:
        logger.warning("Redis error during availability stats: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis unavailable",
        ) from exc

    by_status: dict[AvailabilityStatus, int] = {
        AvailabilityStatus.FREE: 0,
        AvailabilityStatus.PARTIAL: 0,
        AvailabilityStatus.BUSY: 0,
        AvailabilityStatus.UNAVAILABLE: 0,
    }
    last_updated: datetime | None = None
    for record in records:
        by_status[record.status] = by_status.get(record.status, 0) + 1
        if last_updated is None or record.updated_at > last_updated:
            last_updated = record.updated_at

    return AvailabilityStatsResponse(
        total=len(records),
        by_status=by_status,
        last_updated_at=last_updated.isoformat() if last_updated else None,
    )
