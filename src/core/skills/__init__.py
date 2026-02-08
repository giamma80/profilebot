"""Skill extraction and normalization module."""

from __future__ import annotations

from src.core.skills.dictionary import (
    SkillDictionary,
    SkillDictionaryError,
    SkillEntry,
    load_skill_dictionary,
)
from src.core.skills.extractor import SkillExtractor
from src.core.skills.normalizer import (
    FUZZY_THRESHOLD,
    AliasMatcher,
    ExactMatcher,
    FuzzyMatcher,
    SkillNormalizer,
)
from src.core.skills.schemas import NormalizedSkill, SkillExtractionResult

__all__ = [
    "FUZZY_THRESHOLD",
    "AliasMatcher",
    "ExactMatcher",
    "FuzzyMatcher",
    "NormalizedSkill",
    "SkillDictionary",
    "SkillDictionaryError",
    "SkillEntry",
    "SkillExtractionResult",
    "SkillExtractor",
    "SkillNormalizer",
    "load_skill_dictionary",
]
