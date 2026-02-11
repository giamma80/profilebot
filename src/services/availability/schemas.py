"""Schemas for canonical availability status records."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AvailabilityStatus(StrEnum):
    """Supported availability states."""

    FREE = "free"
    PARTIAL = "partial"
    BUSY = "busy"
    UNAVAILABLE = "unavailable"


class ProfileAvailability(BaseModel):
    """Availability snapshot for a resource."""

    res_id: int = Field(..., ge=1)
    status: AvailabilityStatus
    allocation_pct: int = Field(..., ge=0, le=100)
    current_project: str | None = None
    available_from: date | None = None
    available_to: date | None = None
    manager_name: str | None = None
    updated_at: datetime

    model_config = {"extra": "forbid"}
