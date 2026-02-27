"""Schemas for the job matching service."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SkillRequirement(BaseModel):
    """A single skill extracted from a job description."""

    skill: str
    importance: Literal["must_have", "nice_to_have"]


class JDAnalysis(BaseModel):
    """Result of LLM-based job description analysis."""

    must_have: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    seniority: Literal["junior", "mid", "senior", "any"] = "any"
    domain: str | None = None

    model_config = {"extra": "forbid"}

    @property
    def all_skills(self) -> list[str]:
        """Return all skills (must_have + nice_to_have)."""
        return self.must_have + self.nice_to_have

    def to_requirements(self) -> list[SkillRequirement]:
        """Convert to a flat list of SkillRequirement."""
        reqs = [SkillRequirement(skill=s, importance="must_have") for s in self.must_have]
        reqs.extend(SkillRequirement(skill=s, importance="nice_to_have") for s in self.nice_to_have)
        return reqs


class CandidateMatch(BaseModel):
    """A single ranked candidate from the matching pipeline."""

    cv_id: str
    res_id: int
    overall_score: float = Field(ge=0.0, le=1.0)
    matched_skills: list[str]
    missing_skills: list[str]
    explanation: str = ""
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class JobMatchRequest(BaseModel):
    """API request for job matching."""

    job_description: str = Field(..., min_length=10)
    max_candidates: int = Field(default=5, ge=1, le=20)
    availability_filter: str = Field(default="free_or_partial")
    include_explanation: bool = True

    model_config = {"extra": "forbid"}


class JobMatchResponse(BaseModel):
    """API response for job matching."""

    extracted_requirements: list[SkillRequirement]
    candidates: list[CandidateMatch]
    no_match_reason: str | None = None
    query_time_ms: int = Field(default=0, ge=0)

    model_config = {"extra": "forbid"}


__all__ = [
    "CandidateMatch",
    "JDAnalysis",
    "JobMatchRequest",
    "JobMatchResponse",
    "SkillRequirement",
]
