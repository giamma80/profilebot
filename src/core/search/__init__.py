"""Search utilities for fallback and fusion."""

from __future__ import annotations

from src.core.search.fallback import recover_skills_from_dictionary
from src.core.search.skill_dictionary_index import index_skills_dictionary

__all__ = ["index_skills_dictionary", "recover_skills_from_dictionary"]
