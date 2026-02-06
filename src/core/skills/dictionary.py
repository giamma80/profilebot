"""Skill dictionary loader and validator."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class SkillDictionaryError(ValueError):
    """Raised when the skills dictionary is invalid."""


@dataclass(frozen=True)
class SkillEntry:
    """Single skill entry from the dictionary."""

    canonical: str
    domain: str
    aliases: list[str]
    related: list[str]
    certifications: list[str]


@dataclass(frozen=True)
class SkillDictionaryMeta:
    """Metadata for the skills dictionary."""

    version: str
    updated_at: datetime | None
    domains: list[str]


class SkillDictionary:
    """In-memory skill dictionary with lookup helpers."""

    def __init__(
        self,
        meta: SkillDictionaryMeta,
        skills: dict[str, SkillEntry],
        alias_map: dict[str, SkillEntry],
    ) -> None:
        self._meta = meta
        self._skills = skills
        self._alias_map = alias_map

    @property
    def version(self) -> str:
        """Return the dictionary version."""
        return self._meta.version

    @property
    def domains(self) -> list[str]:
        """Return supported domains."""
        return list(self._meta.domains)

    @property
    def canonical_count(self) -> int:
        """Return the number of canonical skills."""
        return len(self._skills)

    def get_by_canonical(self, name: str) -> SkillEntry | None:
        """Return a skill entry by canonical name."""
        return self._skills.get(name)

    def get_by_alias(self, alias: str) -> SkillEntry | None:
        """Return a skill entry by alias."""
        return self._alias_map.get(alias)

    def get_by_name(self, name: str) -> SkillEntry | None:
        """Return a skill entry by canonical or alias."""
        return self._skills.get(name) or self._alias_map.get(name)

    def all_names(self) -> list[str]:
        """Return all searchable names (canonical + aliases)."""
        return list({*self._skills.keys(), *self._alias_map.keys()})


def load_skill_dictionary(path: str | Path) -> SkillDictionary:
    """Load and validate a skills dictionary YAML file.

    Args:
        path: Path to the YAML dictionary file.

    Returns:
        Loaded SkillDictionary instance.

    Raises:
        SkillDictionaryError: If the file is missing or invalid.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise SkillDictionaryError(f"Dictionary not found: {file_path}")

    try:
        payload = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        raise SkillDictionaryError(f"Failed to read dictionary: {file_path}") from exc

    _validate_payload(payload)

    meta = _build_meta(payload)
    skills, alias_map = _build_entries(payload, meta.domains)

    logger.info(
        "Loaded skills dictionary version %s with %d skills",
        meta.version,
        len(skills),
    )

    return SkillDictionary(meta=meta, skills=skills, alias_map=alias_map)


def _validate_payload(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise SkillDictionaryError("Dictionary must be a YAML mapping")

    required_keys = {"version", "updated_at", "domains", "skills"}
    missing = required_keys - set(payload.keys())
    if missing:
        raise SkillDictionaryError(f"Missing required keys: {sorted(missing)}")

    if not isinstance(payload["version"], str) or not payload["version"].strip():
        raise SkillDictionaryError("version must be a non-empty string")

    if not isinstance(payload["domains"], list) or not payload["domains"]:
        raise SkillDictionaryError("domains must be a non-empty list")

    normalized_domains = [str(domain).strip().lower() for domain in payload["domains"]]
    normalized_domains = [domain for domain in normalized_domains if domain]
    if len(normalized_domains) != len(set(normalized_domains)):
        raise SkillDictionaryError("domains must be unique and non-empty")

    if not isinstance(payload["skills"], dict) or not payload["skills"]:
        raise SkillDictionaryError("skills must be a non-empty mapping")


def _build_meta(payload: dict[str, Any]) -> SkillDictionaryMeta:
    updated_at_raw = payload.get("updated_at")
    updated_at = None
    if isinstance(updated_at_raw, str):
        try:
            updated_at = datetime.fromisoformat(updated_at_raw)
        except ValueError:
            logger.warning("Invalid updated_at format: '%s'", updated_at_raw)

    domains = [str(domain).strip().lower() for domain in payload["domains"] if str(domain).strip()]

    return SkillDictionaryMeta(
        version=payload["version"].strip(),
        updated_at=updated_at,
        domains=domains,
    )


def _build_entries(
    payload: dict[str, Any],
    domains: list[str],
) -> tuple[dict[str, SkillEntry], dict[str, SkillEntry]]:
    skills: dict[str, SkillEntry] = {}
    alias_map: dict[str, SkillEntry] = {}

    for raw_key, raw_entry in payload["skills"].items():
        if not isinstance(raw_entry, dict):
            raise SkillDictionaryError(f"Skill '{raw_key}' must be a mapping")

        canonical = _normalize_name(raw_entry.get("canonical") or raw_key)
        domain = _normalize_name(raw_entry.get("domain") or "")
        if not domain:
            raise SkillDictionaryError(f"Skill '{canonical}' missing domain")
        if domain not in domains:
            raise SkillDictionaryError(f"Skill '{canonical}' has unknown domain '{domain}'")

        aliases = _normalize_list(raw_entry.get("aliases", []))
        related = _normalize_list(raw_entry.get("related", []))
        certifications = _normalize_list(raw_entry.get("certifications", []))

        if canonical in skills:
            raise SkillDictionaryError(f"Duplicate canonical skill: '{canonical}'")

        entry = SkillEntry(
            canonical=canonical,
            domain=domain,
            aliases=aliases,
            related=related,
            certifications=certifications,
        )
        skills[canonical] = entry

        for alias in aliases:
            if alias in alias_map or alias in skills:
                raise SkillDictionaryError(f"Duplicate alias or canonical: '{alias}'")
            alias_map[alias] = entry

    return skills, alias_map


def _normalize_name(value: Any) -> str:
    return str(value).strip().lower()


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise SkillDictionaryError("List fields must be arrays")
    normalized = []
    for item in value:
        item_str = str(item).strip().lower()
        if item_str:
            normalized.append(item_str)
    return normalized


__all__ = [
    "SkillDictionary",
    "SkillDictionaryError",
    "SkillEntry",
    "load_skill_dictionary",
]
