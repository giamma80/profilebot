"""Schemas for ingestion status responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IngestionStatusResponse(BaseModel):
    """Response payload for ingestion status by res_id."""

    res_id: int = Field(..., ge=1, description="Resource identifier")
    last_ingested_at: datetime | None = Field(
        default=None,
        description="Last time ingestion pipeline ran",
    )
    is_fresh: bool = Field(..., description="Whether the res_id is within freshness TTL")
    staleness_seconds: int | None = Field(
        default=None,
        ge=0,
        description="Seconds since last ingestion run",
    )

    model_config = {"extra": "forbid"}


__all__ = ["IngestionStatusResponse"]
