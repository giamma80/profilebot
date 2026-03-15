"""Debug script to inspect ParsedCV output for a res_id."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from src.core.parser import parse_docx_bytes
from src.core.parser.schemas import ParsedCV
from src.services.scraper.client import ScraperClient

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for the debug script."""
    parser = argparse.ArgumentParser(
        description="Download a CV by res_id and dump the parsed output.",
    )
    parser.add_argument(
        "res_id",
        type=int,
        help="Resource identifier to debug.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Trigger scraper refresh before downloading the CV.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write parsed CV JSON output.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level.",
    )
    return parser


def _summarize(parsed_cv: ParsedCV) -> dict[str, int]:
    """Summarize parsed CV sections for debugging.

    Args:
        parsed_cv: Parsed CV payload.

    Returns:
        Summary metrics for skills/experience/raw text.
    """
    skills_keywords_count = (
        len(parsed_cv.skills.skill_keywords)
        if parsed_cv.skills and parsed_cv.skills.skill_keywords
        else 0
    )
    skills_raw_text_len = (
        len(parsed_cv.skills.raw_text.strip())
        if parsed_cv.skills and parsed_cv.skills.raw_text
        else 0
    )
    experiences_total = len(parsed_cv.experiences)
    experiences_with_description = sum(
        1
        for experience in parsed_cv.experiences
        if experience.description and experience.description.strip()
    )
    raw_text_len = len(parsed_cv.raw_text.strip()) if parsed_cv.raw_text else 0
    return {
        "raw_text_len": raw_text_len,
        "skills_keywords": skills_keywords_count,
        "skills_raw_text_len": skills_raw_text_len,
        "experiences": experiences_total,
        "experiences_with_description": experiences_with_description,
    }


def main() -> int:
    """Run the debug workflow."""
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))

    res_id = args.res_id
    with ScraperClient() as client:
        if args.refresh:
            logger.info("Refreshing CV for res_id %s", res_id)
            client.refresh_inside_cv(res_id)
        logger.info("Downloading CV for res_id %s", res_id)
        docx_bytes = client.download_inside_cv(res_id)

    parsed_cv = parse_docx_bytes(docx_bytes, res_id)
    summary = _summarize(parsed_cv)

    logger.info(
        "Parsed CV summary for res_id %s: raw_text_len=%d skills_keywords=%d skills_raw_text_len=%d experiences=%d experiences_with_description=%d",
        res_id,
        summary["raw_text_len"],
        summary["skills_keywords"],
        summary["skills_raw_text_len"],
        summary["experiences"],
        summary["experiences_with_description"],
    )

    payload = parsed_cv.model_dump(mode="json")
    serialized = json.dumps(payload, indent=2, ensure_ascii=False)

    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
        logger.info("Wrote parsed CV JSON to %s", args.output)
    else:
        print(serialized)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
