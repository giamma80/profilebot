"""API endpoint for profile analysis details."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.services.analysis import (
    ProfileAnalysisNotFoundError,
    ProfileAnalysisService,
    ProfileAnalysisUnavailableError,
)
from src.services.analysis.schemas import ProfessionalRole, SeniorityLevel

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])

logger = logging.getLogger(__name__)


class ProfileAnalysisResponse(BaseModel):
    """Response payload for profile analysis."""

    res_id: int = Field(..., ge=1)
    seniority_inferred: SeniorityLevel | None = None
    role_inferred: ProfessionalRole | None = None
    profile_strength: float = Field(..., ge=0.0, le=1.0)
    top_skills: list[str]
    skill_gaps: list[str] | None = None
    reskilling_summary: str | None = None
    analysis_notes: str | None = None

    model_config = {"extra": "forbid"}


@router.get(
    "/{res_id}/analysis",
    response_model=ProfileAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Ottieni analisi profilo per res_id",
)
def get_profile_analysis(res_id: int) -> ProfileAnalysisResponse:
    """Return profile analysis for a given res_id."""
    if res_id < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="res_id must be positive",
        )

    service = ProfileAnalysisService()
    try:
        payload = service.get_analysis(res_id)
    except ProfileAnalysisNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="res_id not found",
        ) from exc
    except ProfileAnalysisUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Profile analysis service unavailable",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error in profile analysis")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore interno nel servizio di analisi.",
        ) from exc

    return ProfileAnalysisResponse(**payload)
