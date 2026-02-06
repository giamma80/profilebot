"""CLI entrypoint for the CV parser module."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from src.core.parser.docx_parser import CVParseError, parse_docx


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse a DOCX CV and print structured output.")
    parser.add_argument("path", type=Path, help="Path to the DOCX file to parse")
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))

    try:
        parsed = parse_docx(args.path)
    except CVParseError as exc:
        print(f"CVParseError: {exc}")
        return 1

    payload = parsed.model_dump()
    if args.pretty:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(payload, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
