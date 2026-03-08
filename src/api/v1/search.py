"""Search endpoints for skill-based queries."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from src.api.v1.schemas import ProfileMatch, SkillSearchRequest, SkillSearchResponse
from src.services.search.skill_search import ProfileMatch as ServiceProfileMatch
from src.services.search.skill_search import SearchFilters as ServiceSearchFilters
from src.services.search.skill_search import search_by_skills

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.post(
    "/skills",
    response_model=SkillSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Cerca profili per skill",
)
def search_profiles_by_skills(request: SkillSearchRequest) -> SkillSearchResponse:
    """Search profiles by skills with optional filters."""
    filters = None
    if request.filters is not None:
        filters = ServiceSearchFilters(
            res_ids=request.filters.res_ids,
            skill_domains=request.filters.skill_domains,
            seniority=request.filters.seniority,
            availability=request.filters.availability,
        )

    def _map_matches(matches: list[ServiceProfileMatch] | None) -> list[ProfileMatch] | None:
        if matches is None:
            return None
        return [
            ProfileMatch(
                res_id=match.res_id,
                cv_id=match.cv_id,
                score=match.score,
                matched_skills=match.matched_skills,
                missing_skills=match.missing_skills,
            )
            for match in matches
        ]

    try:
        response = search_by_skills(
            skills=request.skills,
            filters=filters,
            limit=request.limit,
            offset=request.offset,
        )
    except ValueError as exc:
        logger.warning("Invalid search request: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return SkillSearchResponse(
        results=_map_matches(response.results) or [],
        total=response.total,
        limit=response.limit,
        offset=response.offset,
        query_time_ms=response.query_time_ms,
        candidates_by_skills=_map_matches(response.candidates_by_skills),
        candidates_by_chunks=_map_matches(response.candidates_by_chunks),
        candidates_fused=_map_matches(response.candidates_fused),
        fallback_activated=response.fallback_activated,
        recovered_skills=response.recovered_skills,
        no_match_reason=response.no_match_reason,
        fusion_strategy=response.fusion_strategy,
        search_metadata=response.search_metadata,
    )
