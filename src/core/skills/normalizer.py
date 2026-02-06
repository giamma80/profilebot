"""Skill normalizer with exact, alias, and fuzzy matching strategies."""

from __future__ import annotations

import logging
from typing import Literal

from rapidfuzz import fuzz, process

from src.core.skills.dictionary import SkillDictionary, SkillEntry
from src.core.skills.schemas import NormalizedSkill

logger = logging.getLogger(__name__)

FUZZY_THRESHOLD = 85


class ExactMatcher:
    """Match skills by exact canonical name."""

    def __init__(self, dictionary: SkillDictionary) -> None:
        self._dictionary = dictionary

    def match(self, cleaned: str) -> SkillEntry | None:
        """Return a skill entry if the canonical name matches."""
        return self._dictionary.get_by_canonical(cleaned)


class AliasMatcher:
    """Match skills by known aliases."""

    def __init__(self, dictionary: SkillDictionary) -> None:
        self._dictionary = dictionary

    def match(self, cleaned: str) -> SkillEntry | None:
        """Return a skill entry if an alias matches."""
        return self._dictionary.get_by_alias(cleaned)


class FuzzyMatcher:
    """Match skills using fuzzy string similarity."""

    def __init__(
        self,
        dictionary: SkillDictionary,
        threshold: int = FUZZY_THRESHOLD,
    ) -> None:
        self._dictionary = dictionary
        self._threshold = threshold
        self._all_names = dictionary.all_names()

    def match(self, cleaned: str) -> tuple[SkillEntry, float] | None:
        """Return a skill entry and confidence if fuzzy matched."""
        if not self._all_names:
            return None

        result = process.extractOne(
            cleaned,
            self._all_names,
            scorer=fuzz.ratio,
        )
        if not result:
            return None

        match, score, _ = result
        if score < self._threshold:
            return None

        skill = self._dictionary.get_by_name(match)
        if skill is None:
            logger.warning("Fuzzy match not found in dictionary for '%s'", match)
            return None

        return skill, score / 100


class SkillNormalizer:
    """Normalize raw skills using a dictionary and matching strategies."""

    def __init__(self, dictionary: SkillDictionary) -> None:
        """Initialize the normalizer with a skill dictionary.

        Args:
            dictionary: Loaded skill dictionary.
        """
        self._dictionary = dictionary
        self._exact_matcher = ExactMatcher(dictionary)
        self._alias_matcher = AliasMatcher(dictionary)
        self._fuzzy_matcher = FuzzyMatcher(dictionary, threshold=FUZZY_THRESHOLD)

    def normalize(self, raw_skill: str) -> NormalizedSkill | None:
        """Normalize a raw skill string into a canonical skill.

        Args:
            raw_skill: Raw skill text.

        Returns:
            NormalizedSkill if matched, otherwise None.
        """
        cleaned = self._clean(raw_skill)
        if not cleaned:
            return None

        if skill := self._exact_matcher.match(cleaned):
            return self._build_result(raw_skill, skill, confidence=1.0, match_type="exact")

        if skill := self._alias_matcher.match(cleaned):
            return self._build_result(raw_skill, skill, confidence=0.95, match_type="alias")

        fuzzy_match = self._fuzzy_matcher.match(cleaned)
        if fuzzy_match is not None:
            skill, confidence = fuzzy_match
            return self._build_result(
                raw_skill,
                skill,
                confidence=confidence,
                match_type="fuzzy",
            )

        return None

    @staticmethod
    def _clean(text: str) -> str:
        """Normalize input text for matching."""
        return text.strip().lower()

    @staticmethod
    def _build_result(
        raw_skill: str,
        entry: SkillEntry,
        confidence: float,
        match_type: Literal["exact", "alias", "fuzzy"],
    ) -> NormalizedSkill:
        """Create a NormalizedSkill from a dictionary entry."""
        return NormalizedSkill(
            original=raw_skill,
            canonical=entry.canonical,
            domain=entry.domain,
            confidence=confidence,
            match_type=match_type,
        )


__all__ = [
    "AliasMatcher",
    "ExactMatcher",
    "FuzzyMatcher",
    "SkillNormalizer",
    "FUZZY_THRESHOLD",
]
