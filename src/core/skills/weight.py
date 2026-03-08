"""Skill weighting models and helpers."""

from __future__ import annotations

from math import log
from typing import Literal

from pydantic import BaseModel, Field, model_validator

SkillLevel = Literal["junior", "intermediate", "senior", "expert"]

_BASE_WEIGHT = 1.0
_CERT_BONUS = 0.5


def calculate_years_factor(years: float) -> float:
    """Calculate the years factor using a logarithmic scale.

    Args:
        years: Years of experience for the skill.

    Returns:
        Years factor contribution.
    """
    safe_years = max(0.0, years)
    return log(1 + safe_years)


def calculate_skill_weight(years: float, certified: bool) -> float:
    """Calculate the weight for a skill based on experience and certifications.

    Args:
        years: Years of experience for the skill.
        certified: Whether the skill is certified.

    Returns:
        Computed weight score.
    """
    years_factor = calculate_years_factor(years)
    cert_bonus = _CERT_BONUS if certified else 0.0
    return _BASE_WEIGHT + years_factor + cert_bonus


class SkillWeight(BaseModel):
    """Weighted skill representation with experience metadata."""

    name: str = Field(..., description="Normalized skill name")
    years: float = Field(0.0, ge=0.0, description="Years of experience")
    level: SkillLevel = Field("intermediate", description="Skill seniority level")
    certified: bool = Field(False, description="Whether the skill is certified")
    from_experience: bool = Field(True, description="Skill verified by experience")
    years_factor: float = Field(0.0, ge=0.0, description="Years factor")
    cert_bonus: float = Field(0.0, ge=0.0, description="Certification bonus")
    weight: float = Field(0.0, ge=0.0, description="Computed weight")

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _compute_weight(self) -> SkillWeight:
        self.years_factor = calculate_years_factor(self.years)
        self.cert_bonus = _CERT_BONUS if self.certified else 0.0
        self.weight = calculate_skill_weight(self.years, self.certified)
        return self

    @property
    def total_weight(self) -> float:
        """Return the total weight for the skill."""
        return self.weight


__all__ = [
    "SkillLevel",
    "SkillWeight",
    "calculate_skill_weight",
    "calculate_years_factor",
]
