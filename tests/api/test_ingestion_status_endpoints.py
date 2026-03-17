from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.services.ingestion.status_schemas import IngestionStatusResponse
from src.services.ingestion.status_service import IngestionStatusError


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_get_ingestion_status__success_returns_payload(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class DummyService:
        def get_status(self, res_id: int) -> IngestionStatusResponse:
            return IngestionStatusResponse(
                res_id=res_id,
                last_ingested_at=datetime.now(UTC) - timedelta(minutes=5),
                is_fresh=True,
                staleness_seconds=300,
            )

    monkeypatch.setattr("src.api.v1.ingestion_status.IngestionStatusService", DummyService)

    response = client.get("/api/v1/ingestion/status/10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["res_id"] == 10
    assert payload["is_fresh"] is True
    assert payload["staleness_seconds"] == 300
    assert payload["last_ingested_at"] is not None


def test_get_ingestion_status__invalid_res_id_returns_400(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class DummyService:
        def get_status(self, _res_id: int) -> IngestionStatusResponse:
            raise ValueError("res_id must be a positive integer")

    monkeypatch.setattr("src.api.v1.ingestion_status.IngestionStatusService", DummyService)

    response = client.get("/api/v1/ingestion/status/0")

    assert response.status_code == 400
    assert response.json()["detail"] == "res_id must be a positive integer"


def test_get_ingestion_status__service_error_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class DummyService:
        def get_status(self, _res_id: int) -> IngestionStatusResponse:
            raise IngestionStatusError("Redis unavailable for ingestion status")

    monkeypatch.setattr("src.api.v1.ingestion_status.IngestionStatusService", DummyService)

    response = client.get("/api/v1/ingestion/status/10")

    assert response.status_code == 503
    assert response.json()["detail"] == "Ingestion status unavailable"
