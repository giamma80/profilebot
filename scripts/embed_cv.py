"""CLI script to embed and index a single CV into Qdrant."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from src.core.embedding.pipeline import EmbeddingPipeline
from src.core.parser import parse_docx
from src.core.skills import SkillExtractor, load_skill_dictionary

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Embed and index a single CV DOCX into Qdrant.",
    )
    parser.add_argument(
        "--cv",
        type=Path,
        required=True,
        help="Path to the CV DOCX file.",
    )
    parser.add_argument(
        "--dictionary",
        type=Path,
        default=Path("data/skills_dictionary.yaml"),
        help="Path to the skills dictionary YAML.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute embeddings without writing to Qdrant.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level.",
    )
    return parser


def main() -> int:
    """Run the single CV embedding pipeline."""
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))

    cv_path: Path = args.cv
    if not cv_path.exists():
        logger.error("CV file does not exist: %s", cv_path)
        return 1
    if cv_path.suffix.lower() != ".docx":
        logger.warning("CV file extension is not .docx: %s", cv_path)

    dictionary_path: Path = args.dictionary
    if not dictionary_path.exists():
        logger.error("Skills dictionary not found: %s", dictionary_path)
        return 1

    parsed_cv = parse_docx(cv_path)
    dictionary = load_skill_dictionary(dictionary_path)
    extractor = SkillExtractor(dictionary)
    skill_result = extractor.extract(parsed_cv)

    pipeline = EmbeddingPipeline()
    result = pipeline.process_cv(parsed_cv, skill_result, dry_run=args.dry_run)

    payload = {
        "cv_id": parsed_cv.metadata.cv_id,
        "file_name": parsed_cv.metadata.file_name,
        "dry_run": args.dry_run,
        "result": result,
    }

    if args.pretty:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(payload, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
