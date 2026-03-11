"""Configurable blacklist for filtering non-skill tokens."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_BLACKLIST_PATH = Path("data/skills_blacklist.yaml")


class SkillBlacklistError(ValueError):
    """Raised when the skills blacklist is invalid."""


@dataclass(frozen=True)
class SkillBlacklist:
    """In-memory blacklist for excluding non-skill tokens."""

    exact: set[str]
    patterns: tuple[re.Pattern[str], ...]

    def is_blocked(self, text: str) -> bool:
        """Return True when the given text should be filtered out.

        Args:
            text: Raw or cleaned token candidate.

        Returns:
            True when token is blacklisted, False otherwise.
        """
        normalized = text.strip().lower()
        if not normalized:
            return False
        if normalized in self.exact:
            return True
        return any(pattern.search(normalized) for pattern in self.patterns)

    @classmethod
    def empty(cls) -> SkillBlacklist:
        """Return an empty blacklist."""
        return cls(exact=set(), patterns=())


def load_skill_blacklist(path: str | Path | None = None) -> SkillBlacklist:
    """Load and validate a skills blacklist YAML file.

    Args:
        path: Optional path to the YAML blacklist file. If None, uses default
            path or the SKILLS_BLACKLIST_PATH environment variable.

    Returns:
        Loaded SkillBlacklist instance (empty if file does not exist).

    Raises:
        SkillBlacklistError: If the file is invalid.
    """
    file_path = _resolve_blacklist_path(path)
    if not file_path.exists():
        logger.info("Skills blacklist not found: %s", file_path)
        return SkillBlacklist.empty()

    try:
        payload = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        raise SkillBlacklistError(f"Failed to read blacklist: {file_path}") from exc

    _validate_payload(payload)

    exact = {item.strip().lower() for item in payload.get("exact", []) if str(item).strip()}
    patterns = tuple(
        re.compile(pattern, re.IGNORECASE)
        for pattern in payload.get("patterns", [])
        if str(pattern).strip()
    )

    logger.info(
        "Loaded skills blacklist with %d exact items and %d patterns", len(exact), len(patterns)
    )
    return SkillBlacklist(exact=exact, patterns=patterns)


def _resolve_blacklist_path(path: str | Path | None) -> Path:
    env_path = os.getenv("SKILLS_BLACKLIST_PATH")
    raw_path = path or env_path or _DEFAULT_BLACKLIST_PATH
    return Path(raw_path)


def _validate_payload(payload: Any) -> None:
    if payload is None:
        raise SkillBlacklistError("Blacklist is empty")
    if not isinstance(payload, dict):
        raise SkillBlacklistError("Blacklist must be a YAML mapping")
    if "exact" in payload and not isinstance(payload["exact"], list):
        raise SkillBlacklistError("Blacklist exact must be a list")
    if "patterns" in payload and not isinstance(payload["patterns"], list):
        raise SkillBlacklistError("Blacklist patterns must be a list")
    updated_at_raw = payload.get("updated_at")
    if isinstance(updated_at_raw, str):
        try:
            datetime.fromisoformat(updated_at_raw)
        except ValueError:
            logger.warning("Invalid updated_at format in blacklist: '%s'", updated_at_raw)


__all__ = ["SkillBlacklist", "SkillBlacklistError", "load_skill_blacklist"]
