"""Cleanup cv_chunks payloads by removing chunk_text."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Iterable

from qdrant_client import QdrantClient

from src.services.qdrant.client import get_qdrant_client

COLLECTION_NAME = "cv_chunks"
PAYLOAD_KEY = "chunk_text"
DEFAULT_BATCH_SIZE = 256

logger = logging.getLogger(__name__)


def _iter_point_ids(
    client: QdrantClient,
    *,
    batch_size: int,
) -> Iterable[list[object]]:
    """Yield batches of point IDs from the target collection."""
    offset: int | str | None = None
    while True:
        records, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=batch_size,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        if not records:
            break
        yield [record.id for record in records]
        if offset is None:
            break


def _payload_field_exists(client: QdrantClient, field_name: str) -> bool:
    """Return True when the payload field is registered in the collection schema."""
    info = client.get_collection(collection_name=COLLECTION_NAME)
    payload_schema = info.payload_schema or {}
    return field_name in payload_schema


def cleanup_chunk_payload(
    client: QdrantClient,
    *,
    batch_size: int,
    dry_run: bool,
) -> int:
    """Remove chunk_text payloads from cv_chunks points.

    Args:
        client: Qdrant client instance.
        batch_size: Number of points per deletion batch.
        dry_run: When True, only counts candidate points.

    Returns:
        Total number of points processed.
    """
    total = 0
    for ids in _iter_point_ids(client, batch_size=batch_size):
        total += len(ids)
        if dry_run:
            continue
        client.delete_payload(
            collection_name=COLLECTION_NAME,
            keys=[PAYLOAD_KEY],
            points=ids,
            wait=True,
        )

    if not dry_run and _payload_field_exists(client, PAYLOAD_KEY):
        client.delete_payload_index(
            collection_name=COLLECTION_NAME,
            field_name=PAYLOAD_KEY,
            wait=True,
        )

    return total


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove chunk_text payloads from cv_chunks points.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Number of points per deletion batch.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count points without modifying payloads.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (e.g., INFO, DEBUG).",
    )
    return parser.parse_args()


def main() -> None:
    """Run the cleanup workflow."""
    args = _parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    client = get_qdrant_client()
    total = cleanup_chunk_payload(
        client,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )
    logger.info("Processed %d points in %s", total, COLLECTION_NAME)
    if args.dry_run:
        logger.info("Dry-run enabled; no payloads were modified.")


if __name__ == "__main__":
    main()
