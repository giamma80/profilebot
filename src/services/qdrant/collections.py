"""Qdrant collection schemas and setup utilities."""

from __future__ import annotations

import os
from collections.abc import Iterable

from qdrant_client import QdrantClient, models

DEFAULT_VECTOR_SIZE = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
DEFAULT_DISTANCE = models.Distance.COSINE


def get_collections_config() -> dict[str, dict]:
    """Return schema configuration for all Qdrant collections."""
    return {
        "cv_skills": {
            "vectors_config": models.VectorParams(
                size=DEFAULT_VECTOR_SIZE,
                distance=DEFAULT_DISTANCE,
            ),
            "payload_schema": {
                "cv_id": models.PayloadSchemaType.KEYWORD,
                "section_type": models.PayloadSchemaType.KEYWORD,
                "normalized_skills": models.PayloadSchemaType.KEYWORD,
                "skill_domain": models.PayloadSchemaType.KEYWORD,
                "seniority_bucket": models.PayloadSchemaType.KEYWORD,
                "dictionary_version": models.PayloadSchemaType.KEYWORD,
                "created_at": models.PayloadSchemaType.DATETIME,
            },
        },
        "cv_experiences": {
            "vectors_config": models.VectorParams(
                size=DEFAULT_VECTOR_SIZE,
                distance=DEFAULT_DISTANCE,
            ),
            "payload_schema": {
                "cv_id": models.PayloadSchemaType.KEYWORD,
                "section_type": models.PayloadSchemaType.KEYWORD,
                "related_skills": models.PayloadSchemaType.KEYWORD,
                "experience_years": models.PayloadSchemaType.INTEGER,
                "created_at": models.PayloadSchemaType.DATETIME,
            },
        },
    }


def ensure_collections(client: QdrantClient) -> None:
    """Create collections and payload indexes if missing."""
    configs = get_collections_config()

    for collection_name, config in configs.items():
        if not _collection_exists(client, collection_name):
            client.create_collection(
                collection_name=collection_name,
                vectors_config=config["vectors_config"],
            )

        _ensure_payload_indexes(
            client=client,
            collection_name=collection_name,
            payload_schema=config["payload_schema"],
        )


def _collection_exists(client: QdrantClient, collection_name: str) -> bool:
    collections = client.get_collections().collections
    return any(item.name == collection_name for item in collections)


def _ensure_payload_indexes(
    client: QdrantClient,
    collection_name: str,
    payload_schema: dict[str, models.PayloadSchemaType],
) -> None:
    existing_fields = _get_existing_payload_fields(client, collection_name)

    for field_name, field_schema in payload_schema.items():
        if field_name in existing_fields:
            continue
        client.create_payload_index(
            collection_name=collection_name,
            field_name=field_name,
            field_schema=field_schema,
        )


def _get_existing_payload_fields(
    client: QdrantClient,
    collection_name: str,
) -> Iterable[str]:
    info = client.get_collection(collection_name=collection_name)
    payload_schema = info.payload_schema or {}
    return payload_schema.keys()
