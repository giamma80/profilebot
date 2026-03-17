from __future__ import annotations

import json
from typing import Any, cast

import pytest

from src.core.llm.client import LLMDecisionClient
from src.services.analysis.service import (
    ProfileAnalysisNotFoundError,
    ProfileAnalysisService,
    ProfileAnalysisUnavailableError,
)
from src.services.reskilling import schemas as reskilling_schemas
from src.services.reskilling.service import ReskillingService


class FakeQdrantClient:
    def __init__(
        self,
        *,
        skills_records: list[dict[str, Any]] | None = None,
        experience_records: list[dict[str, Any]] | None = None,
        raise_error: bool = False,
    ) -> None:
        self._skills_records = skills_records or []
        self._experience_records = experience_records or []
        self._raise_error = raise_error

    def scroll(self, *, collection_name: str, **_kwargs: Any) -> tuple[list[dict[str, Any]], None]:
        if self._raise_error:
            raise RuntimeError("Qdrant unavailable")
        if collection_name == "cv_skills":
            return self._skills_records, None
        if collection_name == "cv_experiences":
            return self._experience_records, None
        return [], None


class FakeLLMClient:
    def __init__(self, *, response: str | None = None, raise_error: bool = False) -> None:
        self._response = response or "{}"
        self._raise_error = raise_error

    def chat_completion_raw(self, _request: Any) -> str:
        if self._raise_error:
            raise RuntimeError("LLM timeout")
        return self._response


class FakeReskillingService:
    def __init__(self, record: reskilling_schemas.ReskillingRecord | None) -> None:
        self._record = record

    def get(self, _res_id: int) -> reskilling_schemas.ReskillingRecord | None:
        return self._record


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


def _build_experience_payload() -> dict[str, Any]:
    return {
        "experience_years": 2,
        "related_skills": ["python", "fastapi"],
    }


def test_profile_analysis_service__invalid_res_id__raises_value_error() -> None:
    service = ProfileAnalysisService(
        qdrant_client=FakeQdrantClient(skills_records=[]),
        llm_client=cast(LLMDecisionClient, FakeLLMClient(response="{}")),
        reskilling_service=cast(ReskillingService, FakeReskillingService(None)),
    )

    with pytest.raises(ValueError):
        service.get_analysis(0)


def test_profile_analysis_service__qdrant_empty__raises_not_found() -> None:
    service = ProfileAnalysisService(
        qdrant_client=FakeQdrantClient(skills_records=[]),
        llm_client=cast(LLMDecisionClient, FakeLLMClient(response="{}")),
        reskilling_service=cast(ReskillingService, FakeReskillingService(None)),
    )

    with pytest.raises(ProfileAnalysisNotFoundError):
        service.get_analysis(123)


def test_profile_analysis_service__qdrant_failure__raises_unavailable() -> None:
    service = ProfileAnalysisService(
        qdrant_client=FakeQdrantClient(raise_error=True),
        llm_client=cast(LLMDecisionClient, FakeLLMClient(response="{}")),
        reskilling_service=cast(ReskillingService, FakeReskillingService(None)),
    )

    with pytest.raises(ProfileAnalysisUnavailableError):
        service.get_analysis(123)


def test_profile_analysis_service__llm_success__returns_payload() -> None:
    skills_payload = _build_skills_payload()
    experience_payload = _build_experience_payload()
    qdrant = FakeQdrantClient(
        skills_records=[{"payload": skills_payload}],
        experience_records=[{"payload": experience_payload}],
    )
    llm_response = json.dumps(
        {
            "skill_gaps": ["kubernetes", "aws"],
            "analysis_notes": "Esperienza solida in backend e API.",
            "reskilling_summary": "Percorso di reskilling in corso.",
        }
    )
    reskilling_record = reskilling_schemas.ReskillingRecord(
        res_id=123,
        course_name="Kubernetes Fundamentals",
        skill_target="kubernetes",
        status=reskilling_schemas.ReskillingStatus.IN_PROGRESS,
    )
    service = ProfileAnalysisService(
        qdrant_client=qdrant,
        llm_client=cast(LLMDecisionClient, FakeLLMClient(response=llm_response)),
        reskilling_service=cast(ReskillingService, FakeReskillingService(reskilling_record)),
    )

    result = service.get_analysis(123)

    assert result["res_id"] == 123
    assert result["seniority_inferred"] == "senior"
    assert result["top_skills"] == ["python", "fastapi", "docker"]
    assert result["skill_gaps"] == ["kubernetes", "aws"]
    assert result["analysis_notes"] == "Esperienza solida in backend e API."
    assert result["reskilling_summary"] == "Percorso di reskilling in corso."
    assert result["match_score"] == pytest.approx(0.833333, rel=1e-3)


def test_profile_analysis_service__llm_timeout__returns_null_fields() -> None:
    skills_payload = _build_skills_payload()
    qdrant = FakeQdrantClient(skills_records=[{"payload": skills_payload}])
    service = ProfileAnalysisService(
        qdrant_client=qdrant,
        llm_client=cast(LLMDecisionClient, FakeLLMClient(raise_error=True)),
        reskilling_service=cast(ReskillingService, FakeReskillingService(None)),
    )

    result = service.get_analysis(123)

    assert result["top_skills"] == ["python", "fastapi", "docker"]
    assert result["match_score"] == pytest.approx(0.833333, rel=1e-3)
    assert result["skill_gaps"] is None
    assert result["analysis_notes"] is None
    assert result["reskilling_summary"] is None


def test_profile_analysis_service__reskilling_missing__returns_null_reskilling_summary() -> None:
    skills_payload = _build_skills_payload()
    qdrant = FakeQdrantClient(skills_records=[{"payload": skills_payload}])
    llm_response = json.dumps(
        {
            "skill_gaps": ["kubernetes"],
            "analysis_notes": "Esperienza backend coerente.",
            "reskilling_summary": "Dovrebbe essere ignorato.",
        }
    )
    service = ProfileAnalysisService(
        qdrant_client=qdrant,
        llm_client=cast(LLMDecisionClient, FakeLLMClient(response=llm_response)),
        reskilling_service=cast(ReskillingService, FakeReskillingService(None)),
    )

    result = service.get_analysis(123)

    assert result["reskilling_summary"] is None
    assert result["analysis_notes"] == "Esperienza backend coerente."
    assert result["skill_gaps"] == ["kubernetes"]
