"""Schemas for pipeline status reporting."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PipelineStatusResponse(BaseModel):
    """Response payload for pipeline status checks."""

    indexed_count: int = Field(..., ge=0)
    queued_count: int = Field(..., ge=0)
    active_count: int = Field(..., ge=0)
    failed_count: int = Field(..., ge=0)
    status: Literal["healthy", "degraded", "error"]
    warnings: list[str] = Field(default_factory=list)
    last_run_at: datetime | None = None
    last_checked: datetime

    model_config = {"extra": "forbid"}


__all__ = ["PipelineStatusResponse"]
