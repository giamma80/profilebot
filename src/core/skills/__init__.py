"""Skill extraction and normalization module."""

from __future__ import annotations

from src.core.skills.blacklist import (
    SkillBlacklist,
    SkillBlacklistError,
    load_skill_blacklist,
)
from src.core.skills.dictionary import (
    SkillDictionary,
    SkillDictionaryError,
    SkillEntry,
    load_skill_dictionary,
)
from src.core.skills.enricher import enrich_skill_metadata
from src.core.skills.extractor import SkillExtractor
from src.core.skills.normalizer import (
    FUZZY_THRESHOLD,
    AliasMatcher,
    ExactMatcher,
    FuzzyMatcher,
    SkillNormalizer,
)
from src.core.skills.schemas import NormalizedSkill, SkillExtractionResult
from src.core.skills.weight import SkillLevel, SkillWeight, calculate_skill_weight

__all__ = [
    "FUZZY_THRESHOLD",
    "AliasMatcher",
    "ExactMatcher",
    "FuzzyMatcher",
    "NormalizedSkill",
    "SkillBlacklist",
    "SkillBlacklistError",
    "SkillDictionary",
    "SkillDictionaryError",
    "SkillEntry",
    "SkillExtractionResult",
    "SkillExtractor",
    "SkillLevel",
    "SkillNormalizer",
    "SkillWeight",
    "calculate_skill_weight",
    "enrich_skill_metadata",
    "load_skill_blacklist",
    "load_skill_dictionary",
]
