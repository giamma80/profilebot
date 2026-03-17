from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.services.reskilling import schemas as reskilling_schemas


class FakeQdrantClient:
    def __init__(self, *, skills_records: list[dict[str, Any]] | None = None) -> None:
        self._skills_records = skills_records or []

    def scroll(self, *, collection_name: str, **_kwargs: Any) -> tuple[list[dict[str, Any]], None]:
        if collection_name == "cv_skills":
            return self._skills_records, None
        if collection_name == "cv_experiences":
            return [], None
        return [], None


class FakeLLMDecisionClient:
    def __init__(self, *, client: Any | None = None, settings: Any | None = None) -> None:
        self._client = client
        self._settings = settings

    def chat_completion_raw(self, _request: Any) -> str:
        return json.dumps(
            {
                "skill_gaps": ["kubernetes", "aws"],
                "analysis_notes": "Esperienza solida in backend e API.",
                "reskilling_summary": "Percorso di reskilling in corso.",
                "role_inferred": "developer",
            }
        )


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _build_skills_payload(*, res_id: int = 123, cv_id: str = "cv-1") -> dict[str, Any]:
    return {
        "cv_id": cv_id,
        "res_id": res_id,
        "seniority_bucket": "senior",
        "ingested_at": "2024-02-01T00:00:00Z",
        "weighted_skills": [
            {"name": "python", "weight": 0.6},
            {"name": "fastapi", "weight": 0.4},
            {"name": "docker", "weight": 0.2},
        ],
        "experiences_compact": [
            {
                "company": "Acme",
                "role": "Backend Engineer",
                "start_year": 2020,
                "end_year": 2022,
                "is_current": False,
                "description_summary": "Backend development on API services.",
            }
        ],
    }


def test_profile_analysis_endpoint__invalid_res_id__returns_400(client: TestClient) -> None:
    response = client.get("/api/v1/profiles/0/analysis")

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"] == "res_id must be positive"


def test_profile_analysis_endpoint__mocked_dependencies__returns_payload(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    skills_payload = _build_skills_payload()
    qdrant = FakeQdrantClient(skills_records=[{"payload": skills_payload}])

    def _get_qdrant_client() -> FakeQdrantClient:
        return qdrant

    def _create_llm_client(*_args: Any, **_kwargs: Any) -> object:
        return object()

    reskilling_record = reskilling_schemas.ReskillingRecord(
        res_id=123,
        course_name="Kubernetes Fundamentals",
        skill_target="kubernetes",
        status=reskilling_schemas.ReskillingStatus.IN_PROGRESS,
    )

    def _get_reskilling(self, _res_id: int) -> reskilling_schemas.ReskillingRecord | None:
        return reskilling_record

    monkeypatch.setattr("src.services.analysis.service.get_qdrant_client", _get_qdrant_client)
    monkeypatch.setattr("src.services.analysis.service.create_llm_client", _create_llm_client)
    monkeypatch.setattr("src.services.analysis.service.LLMDecisionClient", FakeLLMDecisionClient)
    monkeypatch.setattr("src.services.analysis.service.ReskillingService.get", _get_reskilling)

    response = client.get("/api/v1/profiles/123/analysis")

    assert response.status_code == 200
    payload = response.json()
    assert payload["res_id"] == 123
    assert payload["seniority_inferred"] == "senior"
    assert payload["top_skills"] == ["python", "fastapi", "docker"]
    assert payload["skill_gaps"] == ["kubernetes", "aws"]
    assert payload["analysis_notes"] == "Esperienza solida in backend e API."
    assert payload["reskilling_summary"] == "Percorso di reskilling in corso."
    assert payload["role_inferred"] == "developer"
    assert payload["profile_strength"] == pytest.approx(0.833333, rel=1e-3)
