"""Schemas for Knowledge Profile assembly."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from src.core.seniority.calculator import SeniorityBucket
from src.services.availability.schemas import AvailabilityStatus


class ICSubState(StrEnum):
    """IC (intercontratto) sub-state values."""

    IC_AVAILABLE = "ic_available"
    IC_IN_RESKILLING = "ic_in_reskilling"
    IC_IN_TRANSITION = "ic_in_transition"


class SkillDetail(BaseModel):
    """Skill enriched for Knowledge Profile context."""

    canonical: str
    domain: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    match_type: Literal["exact", "alias", "fuzzy"]
    source: Literal["cv", "reskilling"]
    reskilling_completion_pct: int | None = Field(default=None, ge=0, le=100)
    related_certifications: list[str] = Field(default_factory=list)
    last_used_hint: str | None = None

    model_config = {"extra": "forbid"}


class AvailabilityDetail(BaseModel):
    """Availability details for Knowledge Profile."""

    status: AvailabilityStatus
    allocation_pct: int = Field(..., ge=0, le=100)
    current_project: str | None = None
    available_from: date | None = None
    available_to: date | None = None
    manager_name: str | None = None
    is_intercontratto: bool

    model_config = {"extra": "forbid"}


class ReskillingPath(BaseModel):
    """Reskilling path metadata for Knowledge Profile."""

    course_name: str
    target_skills: list[str]
    completion_pct: int = Field(default=0, ge=0, le=100)
    provider: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool

    model_config = {"extra": "forbid"}


class ExperienceSnapshot(BaseModel):
    """Experience snapshot for Knowledge Profile."""

    company: str | None
    role: str | None
    period: str
    description_summary: str
    related_skills: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class RelevantChunk(BaseModel):
    """Relevant chunk extracted from vector store."""

    text: str
    source_collection: Literal["cv_skills", "cv_experiences"]
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    section_type: str | None = None

    model_config = {"extra": "forbid"}


class KnowledgeProfile(BaseModel):
    """Aggregated Knowledge Profile for LLM context."""

    cv_id: str
    res_id: int
    full_name: str | None
    current_role: str | None
    skills: list[SkillDetail]
    skill_domains: dict[str, int]
    total_skills: int
    unknown_skills: list[str] = Field(default_factory=list)
    seniority_bucket: SeniorityBucket
    years_experience_estimate: int | None = None
    availability: AvailabilityDetail | None = None
    ic_sub_state: ICSubState | None = None
    reskilling_paths: list[ReskillingPath] = Field(default_factory=list)
    has_active_reskilling: bool = False
    experiences: list[ExperienceSnapshot] = Field(default_factory=list)
    relevant_chunks: list[RelevantChunk] = Field(default_factory=list)
    match_score: float = 0.0
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    match_ratio: float = 0.0

    model_config = {"extra": "forbid"}


__all__ = [
    "AvailabilityDetail",
    "ExperienceSnapshot",
    "ICSubState",
    "KnowledgeProfile",
    "RelevantChunk",
    "ReskillingPath",
    "SkillDetail",
]
