"""Tests for Qdrant collection schemas and payload indexes."""

from __future__ import annotations

import pytest
from qdrant_client import QdrantClient, models

from src.services.qdrant import ensure_collections, get_collections_config, get_qdrant_client
from src.services.qdrant.collections import DEFAULT_VECTOR_SIZE


@pytest.fixture(scope="module")
def qdrant_client() -> QdrantClient:
    client = get_qdrant_client()
    ensure_collections(client)
    return client


def _get_vector_size(collection_info: models.CollectionInfo) -> int:
    vectors = collection_info.config.params.vectors
    if isinstance(vectors, dict):
        vector_params = next(iter(vectors.values()))
    else:
        vector_params = vectors
    return int(vector_params.size)


def test_cv_skills_schema__includes_res_id_in_payload_index(
    qdrant_client: QdrantClient,
) -> None:
    info = qdrant_client.get_collection(collection_name="cv_skills")
    payload_schema = info.payload_schema or {}
    assert "res_id" in payload_schema


def test_cv_experiences_schema__includes_res_id_in_payload_index(
    qdrant_client: QdrantClient,
) -> None:
    info = qdrant_client.get_collection(collection_name="cv_experiences")
    payload_schema = info.payload_schema or {}
    assert "res_id" in payload_schema


def test_ensure_collections__creates_both_with_res_id_index(
    qdrant_client: QdrantClient,
) -> None:
    for collection_name in ("cv_skills", "cv_experiences"):
        info = qdrant_client.get_collection(collection_name=collection_name)
        payload_schema = info.payload_schema or {}
        assert "res_id" in payload_schema


def test_cv_skills_schema__vector_size_matches_embedding_dimensions(
    qdrant_client: QdrantClient,
) -> None:
    info = qdrant_client.get_collection(collection_name="cv_skills")
    assert _get_vector_size(info) == DEFAULT_VECTOR_SIZE


def test_collection_names__are_correct(qdrant_client: QdrantClient) -> None:
    expected = set(get_collections_config().keys())
    actual = {collection.name for collection in qdrant_client.get_collections().collections}
    assert expected.issubset(actual)
