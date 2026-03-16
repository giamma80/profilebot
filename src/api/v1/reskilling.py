"""API endpoint for profile reskilling details."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.services.reskilling import schemas as reskilling_schemas
from src.services.reskilling import service as reskilling_service

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


class ReskillingResponse(BaseModel):
    """Response payload for a single reskilling record."""

    res_id: int = Field(..., ge=1)
    course_name: str
    skill_target: str | None = None
    status: reskilling_schemas.ReskillingStatus
    start_date: date | None = None
    end_date: date | None = None
    provider: str | None = None
    completion_pct: int | None = Field(default=None, ge=0, le=100)

    model_config = {"extra": "forbid"}


@router.get(
    "/{res_id}/reskilling",
    response_model=ReskillingResponse,
    status_code=status.HTTP_200_OK,
    summary="Ottieni reskilling per res_id",
)
def get_reskilling(res_id: int) -> ReskillingResponse:
    """Return reskilling record for a given res_id."""
    service = reskilling_service.ReskillingService()
    record = service.get(res_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="res_id not found")

    return ReskillingResponse(**record.model_dump())
