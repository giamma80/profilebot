"""Validate the skills dictionary YAML file."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src.core.skills.dictionary import SkillDictionaryError, load_skill_dictionary

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate skills dictionary YAML.")
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("data/skills_dictionary.yaml"),
        help="Path to the skills dictionary YAML.",
    )
    parser.add_argument(
        "--min-skills",
        type=int,
        default=100,
        help="Minimum number of skills required.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level.",
    )
    return parser


def main() -> int:
    """CLI entrypoint for dictionary validation."""
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))

    if not args.path.exists():
        print(f"Dictionary not found: {args.path}")
        return 1

    try:
        dictionary = load_skill_dictionary(args.path)
    except SkillDictionaryError as exc:
        print(f"Dictionary validation failed: {exc}")
        return 1

    skill_count = len(dictionary.all_names())
    canonical_count = dictionary.canonical_count
    domain_count = len(dictionary.domains)

    if canonical_count < args.min_skills:
        print(f"Validation failed: expected >= {args.min_skills} skills, got {canonical_count}")
        return 1

    logger.info(
        "Dictionary OK: %d canonical skills, %d domains, %d searchable names",
        canonical_count,
        domain_count,
        skill_count,
    )
    print("Dictionary validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
