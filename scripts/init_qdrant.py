#!/usr/bin/env python3
"""Initialize Qdrant collections for ProfileBot."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models


CV_SKILLS_COLLECTION = "cv_skills"
CV_EXPERIENCES_COLLECTION = "cv_experiences"


def _load_env() -> None:
    load_dotenv()


def _get_client() -> QdrantClient:
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    api_key = os.getenv("QDRANT_API_KEY")
    timeout = float(os.getenv("QDRANT_TIMEOUT", "10"))
    return QdrantClient(url=url, api_key=api_key, timeout=timeout)


def _collection_exists(client: QdrantClient, name: str) -> bool:
    collections = client.get_collections().collections
    return any(c.name == name for c in collections)


def _create_cv_skills(client: QdrantClient) -> None:
    client.create_collection(
        collection_name=CV_SKILLS_COLLECTION,
        vectors_config=qdrant_models.VectorParams(
            size=1536,
            distance=qdrant_models.Distance.COSINE,
        ),
    )
    client.create_payload_index(
        collection_name=CV_SKILLS_COLLECTION,
        field_name="cv_id",
        field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
    )
    client.create_payload_index(
        collection_name=CV_SKILLS_COLLECTION,
        field_name="section_type",
        field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
    )
    client.create_payload_index(
        collection_name=CV_SKILLS_COLLECTION,
        field_name="normalized_skills",
        field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
    )
    client.create_payload_index(
        collection_name=CV_SKILLS_COLLECTION,
        field_name="skill_domain",
        field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
    )
    client.create_payload_index(
        collection_name=CV_SKILLS_COLLECTION,
        field_name="seniority_bucket",
        field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
    )
    client.create_payload_index(
        collection_name=CV_SKILLS_COLLECTION,
        field_name="dictionary_version",
        field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
    )
    client.create_payload_index(
        collection_name=CV_SKILLS_COLLECTION,
        field_name="created_at",
        field_schema=qdrant_models.PayloadSchemaType.DATETIME,
    )


def _create_cv_experiences(client: QdrantClient) -> None:
    client.create_collection(
        collection_name=CV_EXPERIENCES_COLLECTION,
        vectors_config=qdrant_models.VectorParams(
            size=1536,
            distance=qdrant_models.Distance.COSINE,
        ),
    )
    client.create_payload_index(
        collection_name=CV_EXPERIENCES_COLLECTION,
        field_name="cv_id",
        field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
    )
    client.create_payload_index(
        collection_name=CV_EXPERIENCES_COLLECTION,
        field_name="section_type",
        field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
    )
    client.create_payload_index(
        collection_name=CV_EXPERIENCES_COLLECTION,
        field_name="related_skills",
        field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
    )
    client.create_payload_index(
        collection_name=CV_EXPERIENCES_COLLECTION,
        field_name="experience_years",
        field_schema=qdrant_models.PayloadSchemaType.INTEGER,
    )
    client.create_payload_index(
        collection_name=CV_EXPERIENCES_COLLECTION,
        field_name="created_at",
        field_schema=qdrant_models.PayloadSchemaType.DATETIME,
    )


def _ensure_collections(client: QdrantClient) -> dict[str, Any]:
    created = {"cv_skills": False, "cv_experiences": False}

    if not _collection_exists(client, CV_SKILLS_COLLECTION):
        _create_cv_skills(client)
        created["cv_skills"] = True

    if not _collection_exists(client, CV_EXPERIENCES_COLLECTION):
        _create_cv_experiences(client)
        created["cv_experiences"] = True

    return created


def main() -> int:
    _load_env()
    client = _get_client()

    try:
        created = _ensure_collections(client)
    except Exception as exc:  # pragma: no cover - top-level safety
        print(f"❌ Failed to initialize Qdrant: {exc}")
        return 1

    for name, was_created in created.items():
        status = "created" if was_created else "already exists"
        print(f"✅ Collection `{name}`: {status}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
