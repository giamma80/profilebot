"""Schemas for reskilling records."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class ReskillingStatus(StrEnum):
    """Supported reskilling course statuses."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PLANNED = "planned"


class ReskillingRecord(BaseModel):
    """Canonical reskilling record for a single course."""

    res_id: int = Field(..., ge=1)
    course_name: str
    skill_target: str | None = None
    status: ReskillingStatus
    start_date: date | None = None
    end_date: date | None = None
    provider: str | None = None
    completion_pct: int | None = Field(default=None, ge=0, le=100)

    model_config = {"extra": "forbid"}


__all__ = ["ReskillingRecord", "ReskillingStatus"]
