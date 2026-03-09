"""CLI to index the skills_dictionary collection in Qdrant."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src.core.search.skill_dictionary_index import index_skills_dictionary
from src.core.skills.dictionary import load_skill_dictionary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Index the skills_dictionary collection from a YAML dictionary.",
    )
    parser.add_argument(
        "--dictionary",
        type=Path,
        default=Path("data/skills_dictionary.yaml"),
        help="Path to the skills dictionary YAML.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of skills to embed per batch.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level.",
    )
    return parser


def main() -> int:
    """CLI entrypoint for skills dictionary indexing."""
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))
    dictionary = load_skill_dictionary(args.dictionary)
    indexed = index_skills_dictionary(dictionary, batch_size=args.batch_size)
    print(f"Indexed {indexed} skills into skills_dictionary.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
