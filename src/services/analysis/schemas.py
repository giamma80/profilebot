"""Schemas for profile analysis outputs."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class SeniorityLevel(StrEnum):
    junior = "junior"
    mid = "mid"
    senior = "senior"
    lead = "lead"


class ProfessionalRole(StrEnum):
    developer = "developer"
    analyst = "analyst"
    architect = "architect"
    project_manager = "project_manager"
    tester = "tester"
    devops = "devops"
    data_scientist = "data_scientist"


class ProfileAnalysisLLMOutput(BaseModel):
    """LLM output for profile analysis."""

    skill_gaps: list[str] | None = None
    analysis_notes: str | None = None
    reskilling_summary: str | None = None
    role_inferred: ProfessionalRole | None = None

    model_config = {"extra": "forbid"}


__all__ = ["ProfessionalRole", "ProfileAnalysisLLMOutput", "SeniorityLevel"]
