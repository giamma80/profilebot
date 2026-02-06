"""Pydantic models for CV parsing output."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class CVMetadata(BaseModel):
    """Metadata extracted from the CV header or file context."""

    cv_id: str = Field(..., description="Unique CV identifier")
    file_name: str = Field(..., description="Original file name")
    full_name: Optional[str] = Field(None, description="Candidate full name")
    current_role: Optional[str] = Field(None, description="Current role or title")
    parsed_at: datetime = Field(default_factory=datetime.utcnow)


class SkillSection(BaseModel):
    """Skill section extracted from the CV."""

    raw_text: str = Field("", description="Raw skills section text")
    skill_keywords: list[str] = Field(default_factory=list, description="Skill keywords")


class ExperienceItem(BaseModel):
    """Single experience item."""

    company: Optional[str] = Field(None, description="Company name")
    role: Optional[str] = Field(None, description="Role or title")
    start_date: Optional[date] = Field(None, description="Start date")
    end_date: Optional[date] = Field(None, description="End date")
    description: str = Field("", description="Experience description")


class ParsedCV(BaseModel):
    """Parsed CV output schema."""

    metadata: CVMetadata
    skills: SkillSection
    experiences: list[ExperienceItem] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    raw_text: str = Field("", description="Full raw text for fallback use")
