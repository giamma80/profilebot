"""Pydantic models for CV parsing output."""

from __future__ import annotations

from datetime import UTC, date, datetime

from pydantic import BaseModel, Field


class CVMetadata(BaseModel):
    """Metadata extracted from the CV header or file context."""

    cv_id: str = Field(..., description="Unique CV identifier")
    res_id: int = Field(..., description="Matricola risorsa (chiave riconciliazione)")
    file_name: str = Field(..., description="Original file name")
    full_name: str | None = Field(None, description="Candidate full name")
    current_role: str | None = Field(None, description="Current role or title")
    parsed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SkillSection(BaseModel):
    """Skill section extracted from the CV."""

    raw_text: str = Field("", description="Raw skills section text")
    skill_keywords: list[str] = Field(default_factory=list, description="Skill keywords")


class ExperienceItem(BaseModel):
    """Single experience item."""

    company: str | None = Field(None, description="Company name")
    role: str | None = Field(None, description="Role or title")
    start_date: date | None = Field(None, description="Start date")
    end_date: date | None = Field(None, description="End date")
    description: str = Field("", description="Experience description")
    is_current: bool = Field(False, description="Whether the role is current")


class ParsedCV(BaseModel):
    """Parsed CV output schema."""

    metadata: CVMetadata
    skills: SkillSection | None = None
    experiences: list[ExperienceItem] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    raw_text: str = Field("", description="Full raw text for fallback use")
