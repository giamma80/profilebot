"""Metadata extraction helpers for CV parsing."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime


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
    re.compile(r"(?i)^([A-Z][a-zà-ù]+)\s+([A-Z][a-zà-ù]+)$"),
]

ROLE_PATTERNS = [
    re.compile(r"(?i)^(?:ruolo|posizione|job\s*title)\s*[:\-]\s*(.+)$"),
    re.compile(r"(?i)^(?:current\s*role|current\s*position)\s*[:\-]\s*(.+)$"),
]

EMAIL_PATTERN = re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b")


def extract_metadata_candidates(lines: Iterable[str]) -> MetadataCandidates:
    """
    Extract metadata candidates from plain text lines.

    This is a best-effort heuristic:
    - Prefer explicit labels (Nome/Cognome, Ruolo/Posizione).
    - Fall back to the first likely full name line (Title Case, two tokens).
    - Ignore email-only lines.
    """
    full_name: str | None = None
    current_role: str | None = None

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if EMAIL_PATTERN.search(line):
            continue

        if full_name is None:
            match = _match_first(NAME_PATTERNS, line)
            if match:
                candidate = match.strip()
                if _is_probable_name(candidate):
                    full_name = candidate

        if current_role is None:
            match = _match_first(ROLE_PATTERNS, line)
            if match:
                current_role = match.strip()

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


def _is_probable_name(candidate: str) -> bool:
    parts = candidate.split()
    if len(parts) < 2:
        return False
    if any(len(p) <= 1 for p in parts):
        return False
    if any(p.isupper() and len(p) > 3 for p in parts):
        return False
    return True


def extract_metadata(text: str) -> ParsedMetadata:
    """
    Extract normalized metadata from raw CV text.

    Uses heuristics on the first lines and generates a best-effort cv_id.
    """
    lines = [line.strip() for line in text.splitlines()]
    candidates = extract_metadata_candidates(lines)
    parsed_at = datetime.utcnow()
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
    timestamp = (parsed_at or datetime.utcnow()).strftime("%Y%m%d%H%M%S")
    base = re.sub(r"[^a-zA-Z0-9_-]+", "-", file_name).strip("-").lower()
    return f"{base}-{timestamp}"
