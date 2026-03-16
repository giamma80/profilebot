"""Schemas for search context extraction."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SearchContext(BaseModel):
    """Structured context extracted from a search query."""

    extracted_skills: list[str] | None = None
    seniority: Literal["junior", "mid", "senior", "lead"] | None = None
    availability_required: bool | None = None
    domain: str | None = None
    role: (
        Literal[
            "developer",
            "analyst",
            "architect",
            "project_manager",
            "tester",
            "devops",
            "data_scientist",
        ]
        | None
    ) = None
    business_context: str | None = Field(default=None, max_length=200)
    raw_query: str | None = None

    model_config = {"extra": "forbid"}


__all__ = ["SearchContext"]
