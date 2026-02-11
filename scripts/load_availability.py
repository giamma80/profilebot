"""CLI to load availability CSV into Redis cache."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.services.availability.cache import AvailabilityCache
from src.services.availability.loader import load_from_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load availability data from a canonical CSV into Redis cache."
    )
    parser.add_argument(
        "--csv",
        required=True,
        help="Path to canonical availability CSV file.",
    )
    parser.add_argument(
        "--ttl",
        type=int,
        default=None,
        help="Override cache TTL in seconds (optional).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    csv_path = Path(args.csv)
    if not csv_path.exists():
        parser.error(f"CSV file not found: {csv_path}")

    cache = AvailabilityCache(ttl_seconds=args.ttl)
    result = load_from_csv(csv_path, cache=cache)

    print(
        "Availability load complete:",
        f"total_rows={result.total_rows}",
        f"loaded={result.loaded}",
        f"skipped={result.skipped}",
        sep=" ",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
