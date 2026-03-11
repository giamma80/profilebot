"""Metadata extraction helpers for CV parsing."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from src.core.parser.section_detector import is_section_heading


@dataclass(frozen=True)
class MetadataCandidates:
    """Holds raw candidates extracted from CV text."""

    full_name: str | None
    current_role: str | None


@dataclass(frozen=True)
class ParsedMetadata:
    """Normalized metadata returned by the extractor."""

    cv_id: str
    full_name: str | None
    current_role: str | None
    parsed_at: datetime


NAME_PATTERNS = [
    re.compile(r"(?i)^(?:nome\s*e\s*cognome|nome|cognome)\s*[:\-]\s*(.+)$"),
]

ROLE_PATTERNS = [
    re.compile(r"(?i)^(?:ruolo|posizione|job\s*title)\s*[:\-]\s*(.+)$"),
    re.compile(r"(?i)^(?:current\s*role|current\s*position)\s*[:\-]\s*(.+)$"),
]

ROLE_KEYWORDS = [
    "developer",
    "engineer",
    "analyst",
    "consultant",
    "manager",
    "architect",
    "scientist",
    "designer",
    "devops",
    "data",
    "backend",
    "frontend",
    "full stack",
    "full-stack",
    "fullstack",
    "qa",
    "test",
    "tester",
    "lead",
    "specialist",
]

ROLE_EXCLUDE_PATTERNS = [
    re.compile(r"(?i)anni\s+di\s+esperienza"),
    re.compile(r"(?i)ultimo\s+aggiornamento"),
    re.compile(r"(?i)^competenze$"),
    re.compile(r"(?i)^sommario$"),
]

EMAIL_PATTERN = re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b")

NAME_PARTICLES = {
    "da",
    "de",
    "dei",
    "del",
    "della",
    "delle",
    "dello",
    "degli",
    "di",
    "dos",
    "das",
    "du",
    "la",
    "le",
    "van",
    "von",
}
NAME_PART_PATTERN = re.compile(r"^[A-ZÀ-Ù][a-zà-ù]+(?:[-'][A-ZÀ-Ù][a-zà-ù]+)*$")
SUMMARY_HEADING_PATTERN = re.compile(r"(?i)^(sommario|profilo|profilo professionale)\b")

MIN_NAME_PARTS = 2
MAX_NAME_PARTS = 5
MIN_PART_LENGTH = 2
MAX_ROLE_LENGTH = 80
MAX_METADATA_SCAN_LINES = 25


def extract_metadata_candidates(lines: Iterable[str]) -> MetadataCandidates:
    """
    Extract metadata candidates from plain text lines.

    This is a best-effort heuristic:
    - Prefer explicit labels (Nome/Cognome, Ruolo/Posizione).
    - Fall back to the first likely full name line.
    - Ignore email-only lines.

    Note: this is a temporary heuristic and will be revisited with LLM section
    classification (issue #76).
    """
    full_name: str | None = None
    current_role: str | None = None
    seen_content = False

    for index, raw in enumerate(lines):
        if index >= MAX_METADATA_SCAN_LINES:
            break
        line = raw.strip()
        if not line or EMAIL_PATTERN.search(line):
            continue
        if seen_content and _is_metadata_section_heading(line):
            break
        seen_content = True

        if full_name is None:
            match = _match_first(NAME_PATTERNS, line)
            if match:
                candidate = match.strip()
                if _is_probable_name(candidate):
                    full_name = candidate
            elif _is_probable_name(line):
                full_name = line

        if current_role is None:
            match = _match_first(ROLE_PATTERNS, line)
            if match:
                current_role = match.strip()
            elif full_name and _is_probable_role(line):
                current_role = line

        if full_name and current_role:
            break

    return MetadataCandidates(full_name=full_name, current_role=current_role)


def _match_first(patterns: Iterable[re.Pattern[str]], line: str) -> str | None:
    for pattern in patterns:
        match = pattern.match(line)
        if match:
            if match.lastindex:
                return match.group(match.lastindex)
            return match.group(0)
    return None


def _is_metadata_section_heading(line: str) -> bool:
    if is_section_heading(line):
        return True
    return SUMMARY_HEADING_PATTERN.search(line) is not None


def _is_valid_name_part(part: str) -> bool:
    if part.lower() in NAME_PARTICLES:
        return True
    if part.isupper():
        return True
    return NAME_PART_PATTERN.match(part) is not None


def _is_probable_name(candidate: str) -> bool:
    parts = candidate.split()
    valid = True
    if len(parts) < MIN_NAME_PARTS or len(parts) > MAX_NAME_PARTS:
        valid = False
    elif any(any(ch.isdigit() for ch in p) for p in parts):
        valid = False
    elif _is_probable_role(candidate):
        valid = False
    elif not all(_is_valid_name_part(part) for part in parts):
        valid = False
    elif any(len(part) < MIN_PART_LENGTH for part in parts if part.lower() not in NAME_PARTICLES):
        valid = False
    else:
        uppercase_indices = [
            i
            for i, part in enumerate(parts)
            if part.isupper() and part.lower() not in NAME_PARTICLES
        ]
        if uppercase_indices:
            if uppercase_indices == list(range(len(parts))):
                valid = True
            elif uppercase_indices != [len(parts) - 1]:
                valid = False

    return valid


def _is_probable_role(candidate: str) -> bool:
    lowered = candidate.lower()
    if len(candidate) > MAX_ROLE_LENGTH:
        return False
    if any(pattern.search(candidate) for pattern in ROLE_EXCLUDE_PATTERNS):
        return False
    return any(keyword in lowered for keyword in ROLE_KEYWORDS)


def extract_metadata(text: str) -> ParsedMetadata:
    """
    Extract normalized metadata from raw CV text.

    Uses heuristics on the first lines and generates a best-effort cv_id.
    """
    lines = [line.strip() for line in text.splitlines()]
    candidates = extract_metadata_candidates(lines)
    parsed_at = datetime.now(UTC)
    base_name = candidates.full_name or _first_non_empty_line(lines) or "cv"
    cv_id = build_cv_id(base_name, parsed_at)

    return ParsedMetadata(
        cv_id=cv_id,
        full_name=candidates.full_name,
        current_role=candidates.current_role,
        parsed_at=parsed_at,
    )


def _first_non_empty_line(lines: Iterable[str]) -> str | None:
    for line in lines:
        if line:
            return line
    return None


def build_cv_id(file_name: str, parsed_at: datetime | None = None) -> str:
    """
    Build a deterministic CV identifier from file name and date.

    If parsed_at is omitted, current UTC timestamp is used.
    """
    timestamp = (parsed_at or datetime.now(UTC)).strftime("%Y%m%d%H%M%S")
    base = re.sub(r"[^a-zA-Z0-9_-]+", "-", file_name).strip("-").lower()
    return f"{base}-{timestamp}"
