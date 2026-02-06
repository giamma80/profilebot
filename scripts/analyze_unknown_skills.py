"""Analyze and report unknown skills from CVs."""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from src.core.parser.docx_parser import CVParseError, parse_docx
from src.core.skills.dictionary import load_skill_dictionary
from src.core.skills.extractor import SkillExtractor

logger = logging.getLogger(__name__)


class UnknownSkillReport:
    """Aggregated unknown skills report."""

    def __init__(self) -> None:
        self._unknown_counter: Counter[str] = Counter()
        self._per_cv: dict[str, list[str]] = {}
        self._processed: int = 0
        self._failed: int = 0

    def add(self, cv_id: str, unknown_skills: list[str]) -> None:
        """Add unknown skills for a CV."""
        self._processed += 1
        if unknown_skills:
            self._per_cv[cv_id] = unknown_skills
            self._unknown_counter.update(unknown_skills)

    def add_failure(self, cv_id: str) -> None:
        """Register a parsing failure for a CV."""
        self._failed += 1
        self._per_cv.setdefault(cv_id, [])

    def to_dict(self, limit: int | None = None) -> dict[str, object]:
        """Serialize the report to a dictionary.

        Args:
            limit: Optional max number of top unknown skills to include.

        Returns:
            Dictionary representation of the report.
        """
        most_common = self._unknown_counter.most_common(limit)
        return {
            "processed": self._processed,
            "failed": self._failed,
            "unique_unknowns": len(self._unknown_counter),
            "top_unknowns": [{"skill": skill, "count": count} for skill, count in most_common],
            "per_cv": self._per_cv,
        }

    def to_csv(self, limit: int | None = None) -> str:
        """Serialize the top unknown skills to CSV.

        Args:
            limit: Optional max number of rows to include.

        Returns:
            CSV formatted string.
        """
        lines = ["skill,count"]
        for skill, count in self._unknown_counter.most_common(limit):
            lines.append(f"{skill},{count}")
        return "\n".join(lines)

    def to_text(self, limit: int | None = None) -> str:
        """Serialize the report to a human-readable string."""
        lines = [
            f"Processed CVs: {self._processed}",
            f"Failed CVs: {self._failed}",
            f"Unique unknown skills: {len(self._unknown_counter)}",
            "",
            "Top unknown skills:",
        ]
        for skill, count in self._unknown_counter.most_common(limit):
            lines.append(f"- {skill}: {count}")
        return "\n".join(lines)


def _iter_docx_files(input_path: Path) -> Iterable[Path]:
    """Yield DOCX files from a file or directory."""
    if input_path.is_file():
        if input_path.suffix.lower() == ".docx":
            yield input_path
        else:
            logger.warning("Skipping non-docx file: '%s'", input_path)
        return

    yield from sorted(input_path.rglob("*.docx"))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze unknown skills from DOCX CVs.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to a DOCX file or a directory containing DOCX files.",
    )
    parser.add_argument(
        "--dictionary",
        type=Path,
        default=Path("data/skills_dictionary.yaml"),
        help="Path to the skills dictionary YAML.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output file path for the report.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv", "text"],
        default="json",
        help="Output format for the report.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Limit the number of top unknown skills in the report.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level.",
    )
    return parser


def _render_report(report: UnknownSkillReport, output_format: str, limit: int | None) -> str:
    if output_format == "csv":
        return report.to_csv(limit)
    if output_format == "text":
        return report.to_text(limit)
    return json.dumps(report.to_dict(limit), indent=2, ensure_ascii=False)


def main() -> int:
    """CLI entrypoint for unknown skills analysis."""
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))

    if not args.input.exists():
        print(f"Input not found: {args.input}")
        return 1

    dictionary = load_skill_dictionary(args.dictionary)
    extractor = SkillExtractor(dictionary)

    report = UnknownSkillReport()

    for docx_path in _iter_docx_files(args.input):
        try:
            parsed = parse_docx(docx_path)
            result = extractor.extract_from_parsed_cv(parsed)
            report.add(parsed.metadata.cv_id, result.unknown_skills)
        except CVParseError as exc:
            logger.warning("Failed to parse '%s': %s", docx_path, exc)
            report.add_failure(docx_path.name)

    output = _render_report(report, args.format, args.limit)

    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
