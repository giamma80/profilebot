"""Pydantic schemas for skill search endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from src.services.pipeline import schemas as pipeline_schemas
from src.services.search import schemas as search_schemas
from src.utils.normalization import normalize_string_list

PipelineStatusResponse = pipeline_schemas.PipelineStatusResponse
SearchContext = search_schemas.SearchContext


class SearchFilters(BaseModel):
    """Optional filters for skill search."""

    res_ids: list[int] | None = None
    skill_domains: list[str] | None = None
    seniority: list[str] | None = None
    availability: str | None = "any"

    model_config = {"extra": "forbid"}

    @field_validator("skill_domains", "seniority", mode="before")
    @classmethod
    def normalize_list_fields(cls, value: object) -> list[str] | None:
        if value is None:
            return None
        if not isinstance(value, list):
            raise ValueError("Expected a list")
        normalized = normalize_string_list(value)
        return normalized or None

    @field_validator("availability", mode="before")
    @classmethod
    def normalize_availability(cls, value: object) -> str | None:
        if value is None:
            return "any"
        cleaned = str(value).strip().lower()
        if not cleaned:
            raise ValueError("Invalid availability value")
        mapping = {
            "totale": "only_free",
            "parziale": "free_or_partial",
            "nessuna disponibilità": "unavailable",
            "nessuna disponibilita": "unavailable",
            "only_free": "only_free",
            "free_or_partial": "free_or_partial",
            "any": "any",
            "unavailable": "unavailable",
        }
        if cleaned not in mapping:
            raise ValueError("Invalid availability value")
        return mapping[cleaned]


class SkillSearchRequest(BaseModel):
    """Request payload for skill search."""

    skills: list[str] = Field(..., min_length=1)
    query: str | None = None
    filters: SearchFilters | None = None
    limit: int = Field(default=10, ge=0)
    offset: int = Field(default=0, ge=0)

    model_config = {"extra": "forbid"}

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_skills(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("Expected a list of skills")
        normalized = normalize_string_list(value)
        if not normalized:
            raise ValueError("At least one skill required")
        return normalized


class ProfileMatch(BaseModel):
    """Single profile match result."""

    res_id: int
    cv_id: str
    score: float = Field(..., ge=0.0, le=1.0)
    matched_skills: list[str]
    missing_skills: list[str]

    model_config = {"extra": "forbid"}


class SearchMetadata(BaseModel):
    """Metadata for multi-layer search responses."""

    query_skills_raw: list[str]
    query_skills_normalized: list[str]
    query_skills_recovered: list[str]
    layers_used: list[str]
    scoring_formula: str
    total_candidates_evaluated: int
    fusion_applied: bool
    elapsed_ms: int

    model_config = {"extra": "forbid"}


class SkillSearchResponse(BaseModel):
    """Response payload for skill search."""

    results: list[ProfileMatch]
    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=0)
    offset: int = Field(..., ge=0)
    query_time_ms: int = Field(..., ge=0)
    candidates_by_skills: list[ProfileMatch] | None = None
    candidates_by_chunks: list[ProfileMatch] | None = None
    candidates_fused: list[ProfileMatch] | None = None
    fallback_activated: bool = False
    recovered_skills: list[str] | None = None
    no_match_reason: str | None = None
    fusion_strategy: str | None = None
    search_metadata: SearchMetadata | None = None
    search_context: SearchContext | None = None

    model_config = {"extra": "ignore"}
