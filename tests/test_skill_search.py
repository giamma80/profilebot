from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar

import pytest
import redis

from src.core.embedding.service import EmbeddingService
from src.core.skills.dictionary import SkillDictionary, SkillDictionaryMeta, SkillEntry
from src.services.availability.schemas import AvailabilityStatus, ProfileAvailability
from src.services.search import skill_search
from src.services.search.skill_search import (
    SearchDependencies,
    SearchFilters,
    _build_filter,
    _get_available_res_ids,
    search_by_skills,
)


@dataclass
class DummyPoint:
    score: float
    payload: dict[str, Any]


class DummyEmbeddingService(EmbeddingService):
    def __init__(self) -> None:
        self._model = "text-embedding-3-small"
        self._dimensions = 3
        self.embed_calls: list[str] = []
        self.embed_batch_calls: list[list[str]] = []

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, text: str) -> list[float]:
        self.embed_calls.append(text)
        return [0.1, 0.2, 0.3]

    def embed_batch(self, texts: Iterable[str]) -> list[list[float]]:
        batch = list(texts)
        self.embed_batch_calls.append(batch)
        return [[0.1, 0.2, 0.3] for _ in batch]


class DummyQdrantClient:
    def __init__(self, points: list[DummyPoint]) -> None:
        self._points = points
        self.query_filter: object | None = None

    def search(self, *, query_filter: object, **_: Any) -> list[DummyPoint]:
        self.query_filter = query_filter
        return self._points


class FakeAvailabilityCache:
    records_by_id: ClassVar[dict[int, ProfileAvailability]] = {}
    records_list: ClassVar[list[ProfileAvailability]] = []

    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    def get_many(self, res_ids: list[int]) -> dict[int, ProfileAvailability]:
        return {
            res_id: self.records_by_id[res_id] for res_id in res_ids if res_id in self.records_by_id
        }

    def scan_records(self) -> list[ProfileAvailability]:
        return list(self.records_list)


class FailingAvailabilityCache:
    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    def get_many(self, *_: Any, **__: Any) -> dict[int, ProfileAvailability]:
        raise redis.RedisError("boom")


def _make_dictionary() -> SkillDictionary:
    meta = SkillDictionaryMeta(version="1.0.0", updated_at=None, domains=["backend"])
    skills = {
        "python": SkillEntry(
            canonical="python",
            domain="backend",
            aliases=[],
            related=[],
            certifications=[],
        ),
        "fastapi": SkillEntry(
            canonical="fastapi",
            domain="backend",
            aliases=[],
            related=[],
            certifications=[],
        ),
        "postgresql": SkillEntry(
            canonical="postgresql",
            domain="backend",
            aliases=[],
            related=[],
            certifications=[],
        ),
    }
    return SkillDictionary(meta=meta, skills=skills, alias_map={})


def _availability(res_id: int, status: AvailabilityStatus) -> ProfileAvailability:
    return ProfileAvailability(
        res_id=res_id,
        status=status,
        allocation_pct=0,
        current_project=None,
        available_from=None,
        updated_at=datetime(2026, 2, 10, 8, 0, 0, tzinfo=UTC),
    )


def test_search_by_skills__ranks_results_and_orders_matched_skills() -> None:
    points = [
        DummyPoint(
            score=0.9,
            payload={
                "cv_id": "cv-1",
                "res_id": 1,
                "normalized_skills": ["python", "fastapi"],
                "skill_domain": "backend",
                "seniority_bucket": "senior",
            },
        ),
        DummyPoint(
            score=0.8,
            payload={
                "cv_id": "cv-2",
                "res_id": 2,
                "normalized_skills": ["python"],
                "skill_domain": "backend",
                "seniority_bucket": "mid",
            },
        ),
    ]
    dependencies = SearchDependencies(
        embedding_service=DummyEmbeddingService(),
        qdrant_client=DummyQdrantClient(points),
        dictionary=_make_dictionary(),
    )

    response = search_by_skills(
        skills=["Python", "FastAPI"],
        filters=None,
        limit=10,
        offset=0,
        dependencies=dependencies,
    )

    assert response.total == 2
    assert response.results[0].res_id == 1
    assert response.results[0].matched_skills == ["python", "fastapi"]
    assert response.results[0].missing_skills == []
    assert response.results[1].res_id == 2
    assert response.results[1].missing_skills == ["fastapi"]


def test_search_by_skills__paginates_results() -> None:
    points = [
        DummyPoint(
            score=0.9, payload={"cv_id": "cv-1", "res_id": 1, "normalized_skills": ["python"]}
        ),
        DummyPoint(
            score=0.8, payload={"cv_id": "cv-2", "res_id": 2, "normalized_skills": ["python"]}
        ),
        DummyPoint(
            score=0.7, payload={"cv_id": "cv-3", "res_id": 3, "normalized_skills": ["python"]}
        ),
    ]
    dependencies = SearchDependencies(
        embedding_service=DummyEmbeddingService(),
        qdrant_client=DummyQdrantClient(points),
        dictionary=_make_dictionary(),
    )

    response = search_by_skills(
        skills=["Python"],
        filters=None,
        limit=1,
        offset=1,
        dependencies=dependencies,
    )

    assert response.total == 3
    assert len(response.results) == 1
    assert response.results[0].res_id == 2


def test_search_by_skills__unknown_skills_raise_value_error() -> None:
    dependencies = SearchDependencies(
        embedding_service=DummyEmbeddingService(),
        qdrant_client=DummyQdrantClient([]),
        dictionary=_make_dictionary(),
    )

    with pytest.raises(ValueError, match="At least one valid skill is required"):
        search_by_skills(
            skills=["unknown"],
            filters=None,
            limit=10,
            offset=0,
            dependencies=dependencies,
        )


def test_get_available_res_ids__filters_by_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeAvailabilityCache.records_by_id = {
        1: _availability(1, AvailabilityStatus.FREE),
        2: _availability(2, AvailabilityStatus.BUSY),
    }
    monkeypatch.setattr(skill_search, "AvailabilityCache", FakeAvailabilityCache)

    result = _get_available_res_ids("only_free", [1, 2])

    assert result == [1]


def test_get_available_res_ids__uses_scan_records_when_no_res_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeAvailabilityCache.records_list = [
        _availability(10, AvailabilityStatus.FREE),
        _availability(11, AvailabilityStatus.UNAVAILABLE),
    ]
    monkeypatch.setattr(skill_search, "AvailabilityCache", FakeAvailabilityCache)

    result = _get_available_res_ids("free_or_partial", None)

    assert result == [10]


def test_build_filter__availability_empty_returns_empty_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeAvailabilityCache.records_list = []
    monkeypatch.setattr(skill_search, "AvailabilityCache", FakeAvailabilityCache)

    filters = SearchFilters(availability="only_free")
    query_filter = _build_filter(filters)

    assert query_filter is not None
    assert query_filter.must[0].key == "res_id"
    assert query_filter.must[0].match.any == [-1]


def test_build_filter__redis_error_keeps_base_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(skill_search, "AvailabilityCache", FailingAvailabilityCache)

    filters = SearchFilters(res_ids=[100, 200], availability="only_free")
    query_filter = _build_filter(filters)

    assert query_filter is not None
    assert len(query_filter.must) == 1
    assert query_filter.must[0].key == "res_id"
    assert query_filter.must[0].match.any == [100, 200]
