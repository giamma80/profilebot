#!/usr/bin/env python3
"""Initialize Qdrant collections for ProfileBot."""

from __future__ import annotations

from dotenv import load_dotenv

from src.services.qdrant import ensure_collections, get_collections_config, get_qdrant_client


def _load_env() -> None:
    load_dotenv()


def _get_existing_collections(client) -> set[str]:
    collections = client.get_collections().collections
    return {collection.name for collection in collections}


def main() -> int:
    _load_env()
    client = get_qdrant_client()

    try:
        existing_before = _get_existing_collections(client)
        ensure_collections(client)
        existing_after = _get_existing_collections(client)
    except Exception as exc:  # pragma: no cover - top-level safety
        print(f"❌ Failed to initialize Qdrant: {exc}")
        return 1

    for name in sorted(get_collections_config().keys()):
        status = (
            "created"
            if name not in existing_before and name in existing_after
            else "already exists"
        )
        print(f"✅ Collection `{name}`: {status}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
