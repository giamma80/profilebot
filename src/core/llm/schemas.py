"""Schemas for LLM requests and decision outputs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LLMRequest(BaseModel):
    """Input payload for an LLM completion call."""

    system_prompt: str
    context: str
    user_prompt: str
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, ge=1)

    model_config = {"extra": "forbid"}


class DecisionCandidate(BaseModel):
    """Candidate information used for decision context building."""

    cv_id: str
    skills: list[str]
    seniority: str
    years_experience: int | None = None
    availability_status: str
    experience_summaries: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class DecisionOutput(BaseModel):
    """Structured decision output returned by the LLM."""

    selected_cv_id: str
    decision_reason: str
    matched_skills: list[str]
    missing_skills: list[str]
    confidence: Literal["high", "medium", "low"]

    model_config = {"extra": "forbid"}


__all__ = ["DecisionCandidate", "DecisionOutput", "LLMRequest"]
