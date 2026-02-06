"""Pydantic schemas for skill normalization and extraction."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class NormalizedSkill(BaseModel):
    """Skill normalizzata con confidence score."""

    original: str = Field(..., description="Skill originale dal CV")
    canonical: str = Field(..., description="Nome canonico normalizzato")
    domain: str = Field(
        ...,
        description="Dominio: backend|frontend|data|devops|management",
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Score confidenza")
    match_type: Literal["exact", "alias", "fuzzy"] = Field(
        ...,
        description="Tipo di match",
    )


class SkillExtractionResult(BaseModel):
    """Risultato estrazione skill da un CV."""

    cv_id: str
    normalized_skills: list[NormalizedSkill]
    unknown_skills: list[str] = Field(default_factory=list)
    dictionary_version: str

    @property
    def skill_count(self) -> int:
        """Return the number of normalized skills."""
        return len(self.normalized_skills)

    @property
    def unknown_count(self) -> int:
        """Return the number of unknown skills."""
        return len(self.unknown_skills)

    def get_stats(self) -> dict[str, float]:
        """Return percentage stats (0-100) for match types and unknown skills."""
        total = len(self.normalized_skills) + len(self.unknown_skills)
        if total == 0:
            return {
                "exact_pct": 0.0,
                "alias_pct": 0.0,
                "fuzzy_pct": 0.0,
                "unknown_pct": 0.0,
            }

        counts = {"exact": 0, "alias": 0, "fuzzy": 0}
        for skill in self.normalized_skills:
            counts[skill.match_type] = counts.get(skill.match_type, 0) + 1

        return {
            "exact_pct": (counts["exact"] / total) * 100,
            "alias_pct": (counts["alias"] / total) * 100,
            "fuzzy_pct": (counts["fuzzy"] / total) * 100,
            "unknown_pct": (len(self.unknown_skills) / total) * 100,
        }


__all__ = ["NormalizedSkill", "SkillExtractionResult"]
