"""Job matching endpoint — POST /api/v1/match/job."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from src.services.matching.matcher import match_job
from src.services.matching.schemas import JobMatchRequest, JobMatchResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/match", tags=["matching"])


@router.post(
    "/job",
    response_model=JobMatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Match profili per Job Description",
    description=(
        "Analizza una job description, estrae le skill richieste, "
        "cerca profili compatibili e li classifica con spiegazione LLM."
    ),
)
def match_job_endpoint(request: JobMatchRequest) -> JobMatchResponse:
    """Match profiles against a job description.

    Pipeline:
        1. LLM extracts skills from JD (must_have / nice_to_have)
        2. Vector search finds matching profiles in Qdrant
        3. LLM ranks and explains top candidates
    """
    try:
        return match_job(request)
    except ValueError as exc:
        logger.warning("Job match request failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error in job match pipeline")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore interno nel matching. Riprova più tardi.",
        ) from exc
