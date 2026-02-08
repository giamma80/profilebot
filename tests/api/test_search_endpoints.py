from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.services.search.skill_search import ProfileMatch, SearchFilters, SkillSearchResponse


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_search_skills__valid_request__returns_ranked_results(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    response_payload = SkillSearchResponse(
        results=[
            ProfileMatch(
                res_id=1001,
                cv_id="cv-1001",
                score=0.92,
                matched_skills=["python", "fastapi"],
                missing_skills=[],
            )
        ],
        total=1,
        limit=10,
        offset=0,
        query_time_ms=42,
    )

    def _search_by_skills(**_: Any) -> SkillSearchResponse:
        return response_payload

    monkeypatch.setattr("src.api.v1.search.search_by_skills", _search_by_skills)

    response = client.post(
        "/api/v1/search/skills",
        json={
            "skills": ["Python", "FastAPI"],
            "filters": {"skill_domains": ["backend"], "seniority": ["senior"]},
            "limit": 10,
            "offset": 0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["results"][0]["res_id"] == 1001
    assert payload["results"][0]["matched_skills"] == ["python", "fastapi"]
    assert payload["query_time_ms"] == 42


def test_search_skills__passes_filters_to_service(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def _search_by_skills(*, filters: SearchFilters | None, **_: Any) -> SkillSearchResponse:
        captured["filters"] = filters
        return SkillSearchResponse(
            results=[],
            total=0,
            limit=10,
            offset=0,
            query_time_ms=1,
        )

    monkeypatch.setattr("src.api.v1.search.search_by_skills", _search_by_skills)

    response = client.post(
        "/api/v1/search/skills",
        json={
            "skills": ["python"],
            "filters": {
                "res_ids": [1001, 1002],
                "skill_domains": ["backend"],
                "seniority": ["mid"],
                "availability": "any",
            },
        },
    )

    assert response.status_code == 200
    filters = captured["filters"]
    assert filters is not None
    assert filters.res_ids == [1001, 1002]
    assert filters.skill_domains == ["backend"]
    assert filters.seniority == ["mid"]
    assert filters.availability == "any"


def test_search_skills__service_validation_error__returns_400(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _search_by_skills(**_: Any) -> SkillSearchResponse:
        raise ValueError("At least one valid skill is required")

    monkeypatch.setattr("src.api.v1.search.search_by_skills", _search_by_skills)

    response = client.post(
        "/api/v1/search/skills",
        json={"skills": ["python"]},
    )

    assert response.status_code == 400


def test_search_skills__performance__returns_under_threshold(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    response_payload = SkillSearchResponse(
        results=[],
        total=0,
        limit=10,
        offset=0,
        query_time_ms=10,
    )

    def _search_by_skills(**_: Any) -> SkillSearchResponse:
        return response_payload

    monkeypatch.setattr("src.api.v1.search.search_by_skills", _search_by_skills)

    start = time.perf_counter()
    response = client.post(
        "/api/v1/search/skills",
        json={"skills": ["python", "fastapi", "postgresql"], "limit": 10, "offset": 0},
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert response.status_code == 200
    assert elapsed_ms < 500
    assert response.json()["query_time_ms"] < 500
