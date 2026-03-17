"""Schemas for profile analysis outputs."""

from __future__ import annotations

from pydantic import BaseModel


class ProfileAnalysisLLMOutput(BaseModel):
    """LLM output for profile analysis."""

    skill_gaps: list[str] | None = None
    analysis_notes: str | None = None
    reskilling_summary: str | None = None

    model_config = {"extra": "forbid"}


__all__ = ["ProfileAnalysisLLMOutput"]
