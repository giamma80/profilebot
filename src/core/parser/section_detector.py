"""Section detection utilities for DOCX CV parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

SECTION_PATTERNS: dict[str, list[str]] = {
    "skills": [
        r"(?i)^(competenze|skills?|technical skills?|conoscenze)",
        r"(?i)^(tecnologie|tools?|linguaggi|frameworks?)",
        r"(?i)^(hard skills|soft skills|competenze tecniche)",
    ],
    "experience": [
        r"(?i)^(esperienza|experience|work history|career)",
        r"(?i)^(esperienze professionali|professional experience)",
        r"(?i)^(posizioni ricoperte|employment)",
    ],
    "education": [
        r"(?i)^(formazione|education|istruzione|studi)",
        r"(?i)^(titoli di studio|qualifiche|academic)",
    ],
    "certifications": [
        r"(?i)^(certificazioni|certifications?|qualifiche)",
        r"(?i)^(attestati|corsi|training)",
    ],
}

DEFAULT_SECTION = "unknown"


@dataclass(frozen=True)
class SectionMatch:
    """Represents a detected section heading."""

    section: str
    heading: str


def detect_section(
    heading: str, patterns: dict[str, list[str]] | None = None
) -> SectionMatch | None:
    """
    Detect the section for a given heading line.

    Returns a SectionMatch if a section is detected, otherwise None.
    """
    if heading is None:
        return None

    normalized = heading.strip()
    if not normalized:
        return None

    pattern_map = patterns or SECTION_PATTERNS
    for section, regexes in pattern_map.items():
        if _matches_any(normalized, regexes):
            return SectionMatch(section=section, heading=normalized)

    return None


def detect_sections(
    lines: Iterable[str],
    patterns: dict[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    """
    Group lines into sections based on detected headings.

    Lines before the first heading are placed under the DEFAULT_SECTION.
    """
    pattern_map = patterns or SECTION_PATTERNS
    sections: dict[str, list[str]] = {key: [] for key in pattern_map}
    sections.setdefault(DEFAULT_SECTION, [])

    current_section = DEFAULT_SECTION
    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        match = detect_section(line, pattern_map)
        if match:
            current_section = match.section
            continue

        sections.setdefault(current_section, []).append(line)

    return sections


def is_section_heading(text: str, patterns: dict[str, list[str]] | None = None) -> bool:
    """Return True if the provided text looks like a section heading."""
    return detect_section(text, patterns) is not None


def normalize_section_name(section: str) -> str:
    """Normalize and validate section names."""
    if not section:
        return DEFAULT_SECTION
    section = section.strip().lower()
    if section in SECTION_PATTERNS:
        return section
    return DEFAULT_SECTION


def _matches_any(text: str, regexes: Iterable[str]) -> bool:
    """Return True if the text matches any regex in the list."""
    for pattern in regexes:
        if re.search(pattern, text):
            return True
    return False
