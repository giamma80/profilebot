from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.core.config import get_settings
from src.services.scraper.client import ScraperClient
from src.services.search.skill_search import ProfileMatch, SkillSearchResponse


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_smoke__core_endpoints__respond_ok(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeInspect:
        def active(self) -> dict[str, Any]:
            return {}

        def reserved(self) -> dict[str, Any]:
            return {}

        def scheduled(self) -> dict[str, Any]:
            return {}

    def _inspect() -> FakeInspect:
        return FakeInspect()

    def _scan_records(self) -> list[Any]:
        return []

    def _search_by_skills(**_: Any) -> SkillSearchResponse:
        return SkillSearchResponse(
            results=[
                ProfileMatch(
                    res_id=1,
                    cv_id="cv-1",
                    score=0.9,
                    matched_skills=["python"],
                    missing_skills=[],
                )
            ],
            total=1,
            limit=10,
            offset=0,
            query_time_ms=5,
        )

    monkeypatch.setattr("src.api.main.get_qdrant_client", lambda: object())
    monkeypatch.setattr("src.api.main.check_qdrant_health", lambda _client: {"status": "ok"})
    monkeypatch.setattr("src.api.v1.embeddings.celery_app.control.inspect", _inspect)
    monkeypatch.setattr("src.api.v1.availability.celery_app.control.inspect", _inspect)
    monkeypatch.setattr("src.api.v1.availability.AvailabilityCache.scan_records", _scan_records)
    monkeypatch.setattr("src.api.v1.search.search_by_skills", _search_by_skills)

    settings = get_settings()
    if not settings.scraper_base_url:
        pytest.fail("SCRAPER_BASE_URL is required for smoke tests")

    with ScraperClient() as scraper_client:
        res_ids = scraper_client.fetch_inside_res_ids()

    assert isinstance(res_ids, list)
    assert all(isinstance(res_id, int) for res_id in res_ids)

    health_response = client.get("/health")
    embeddings_response = client.get("/api/v1/embeddings/stats")
    availability_response = client.get("/api/v1/availability/stats")
    search_response = client.post("/api/v1/search/skills", json={"skills": ["python"]})

    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"

    assert embeddings_response.status_code == 200
    assert set(embeddings_response.json().keys()) == {"active", "reserved", "scheduled"}

    assert availability_response.status_code == 200
    availability_payload = availability_response.json()
    assert availability_payload["total"] == 0
    assert set(availability_payload["by_status"].keys()) == {
        "free",
        "partial",
        "busy",
        "unavailable",
    }

    assert search_response.status_code == 200
    search_payload = search_response.json()
    assert search_payload["total"] == 1
    assert search_payload["results"][0]["res_id"] == 1
