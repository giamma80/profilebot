"""CLI script to embed and index CVs in batch into Qdrant."""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Iterable
from pathlib import Path

from src.core.embedding.pipeline import EmbeddingPipeline
from src.core.parser import parse_docx
from src.core.skills import SkillExtractor, load_skill_dictionary

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Embed and index a batch of CV DOCX files into Qdrant.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing CV DOCX files.",
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
        default=50,
        help="Number of CV files to process per batch.",
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


def _iter_docx_files(directory: Path) -> list[Path]:
    """Collect DOCX files from a directory tree."""
    if not directory.exists():
        return []
    return sorted(directory.rglob("*.docx"))


def _chunked(items: list[Path], batch_size: int) -> Iterable[list[Path]]:
    """Yield items in batches."""
    if batch_size <= 0:
        return []
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


def main() -> int:
    """Run the batch CV embedding pipeline."""
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))

    input_dir: Path = args.input_dir
    if not input_dir.exists():
        logger.error("Input directory does not exist: %s", input_dir)
        return 1

    dictionary_path: Path = args.dictionary
    if not dictionary_path.exists():
        logger.error("Skills dictionary not found: %s", dictionary_path)
        return 1

    cv_files = _iter_docx_files(input_dir)
    if not cv_files:
        logger.warning("No DOCX files found in: %s", input_dir)
        return 0

    dictionary = load_skill_dictionary(dictionary_path)
    extractor = SkillExtractor(dictionary)
    pipeline = EmbeddingPipeline()

    processed = 0
    failed = 0
    totals = {"cv_skills": 0, "cv_experiences": 0, "total": 0}
    errors: list[dict[str, str]] = []

    for batch in _chunked(cv_files, args.batch_size):
        logger.info("Processing batch with %d CVs", len(batch))
        for cv_path in batch:
            try:
                parsed_cv = parse_docx(cv_path)
                skill_result = extractor.extract(parsed_cv)
                result = pipeline.process_cv(parsed_cv, skill_result, dry_run=args.dry_run)
                totals["cv_skills"] += result["cv_skills"]
                totals["cv_experiences"] += result["cv_experiences"]
                totals["total"] += result["total"]
                processed += 1
            except Exception as exc:  # noqa: BLE001 - surface errors per CV
                failed += 1
                logger.exception("Failed processing CV: %s", cv_path)
                errors.append({"file": str(cv_path), "error": str(exc)})

    payload = {
        "input_dir": str(input_dir),
        "dry_run": args.dry_run,
        "processed": processed,
        "failed": failed,
        "totals": totals,
        "errors": errors,
    }

    if args.pretty:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(payload, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
