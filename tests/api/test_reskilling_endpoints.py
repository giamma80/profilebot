from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.services.reskilling import schemas as reskilling_schemas


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_reskilling__record_found__returns_payload(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = reskilling_schemas.ReskillingRecord(
        res_id=123,
        course_name="Kubernetes Fundamentals",
        skill_target="kubernetes",
        status=reskilling_schemas.ReskillingStatus.IN_PROGRESS,
        start_date=date(2024, 1, 1),
        end_date=None,
        provider="CloudAcademy",
        completion_pct=70,
    )

    def _get(self, res_id: int) -> reskilling_schemas.ReskillingRecord | None:
        return record

    monkeypatch.setattr(
        "src.api.v1.reskilling.reskilling_service.ReskillingService.get",
        _get,
    )

    response = client.get("/api/v1/profiles/123/reskilling")

    assert response.status_code == 200
    payload = response.json()
    assert payload["res_id"] == 123
    assert payload["course_name"] == "Kubernetes Fundamentals"
    assert payload["skill_target"] == "kubernetes"
    assert payload["status"] == "in_progress"
    assert payload["start_date"] == "2024-01-01"
    assert payload["end_date"] is None
    assert payload["provider"] == "CloudAcademy"
    assert payload["completion_pct"] == 70


def test_reskilling__record_missing__returns_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _get(self, res_id: int) -> reskilling_schemas.ReskillingRecord | None:
        return None

    monkeypatch.setattr(
        "src.api.v1.reskilling.reskilling_service.ReskillingService.get",
        _get,
    )

    response = client.get("/api/v1/profiles/999/reskilling")

    assert response.status_code == 404
    payload = response.json()
    assert payload["detail"] == "res_id not found"
