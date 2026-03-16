from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.services.pipeline.schemas import PipelineStatusResponse


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


class FakeResult:
    def __init__(self, response: PipelineStatusResponse, failed_sources: int) -> None:
        self.response = response
        self.failed_sources = failed_sources


def test_pipeline_status__healthy__returns_payload(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    response_model = PipelineStatusResponse(
        indexed_count=120,
        queued_count=4,
        active_count=2,
        failed_count=1,
        status="healthy",
        warnings=[],
        last_run_at=datetime(2026, 3, 1, 9, 30, tzinfo=UTC),
        last_checked=datetime(2026, 3, 1, 10, 0, tzinfo=UTC),
    )

    def _get_status(self) -> FakeResult:
        return FakeResult(response=response_model, failed_sources=0)

    monkeypatch.setattr(
        "src.api.v1.pipeline_status.PipelineStatusService.get_status",
        _get_status,
    )

    response = client.get("/api/v1/pipeline/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["indexed_count"] == 120
    assert payload["queued_count"] == 4
    assert payload["active_count"] == 2
    assert payload["status"] == "healthy"
    assert payload["warnings"] == []
    assert payload["failed_count"] == 1
    assert payload["last_run_at"] == "2026-03-01T09:30:00Z"
    assert payload["last_checked"] == "2026-03-01T10:00:00Z"


def test_pipeline_status__all_sources_down__returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    response_model = PipelineStatusResponse(
        indexed_count=0,
        queued_count=0,
        active_count=0,
        failed_count=0,
        status="error",
        warnings=["Qdrant unavailable", "Redis unavailable", "Celery unavailable"],
        last_run_at=None,
        last_checked=datetime(2026, 3, 1, 10, 0, tzinfo=UTC),
    )

    def _get_status(self) -> FakeResult:
        return FakeResult(response=response_model, failed_sources=3)

    monkeypatch.setattr(
        "src.api.v1.pipeline_status.PipelineStatusService.get_status",
        _get_status,
    )

    response = client.get("/api/v1/pipeline/status")

    assert response.status_code == 503
    assert response.json()["detail"] == "Tutti i servizi della pipeline sono irraggiungibili"
