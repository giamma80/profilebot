from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.services.ingestion.profile_service import IngestionOutcome


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_ingest_res_id__service_success__returns_payload(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class DummySettings:
        scraper_base_url = "https://scraper"

    class DummyService:
        def ingest_res_id(self, res_id: int, *, force: bool = False) -> IngestionOutcome:
            return IngestionOutcome(
                status="success",
                res_id=res_id,
                cv_id="cv-123",
                totals={"cv_skills": 1, "cv_experiences": 2, "cv_chunks": 3, "total": 6},
                availability_cached=True,
                reskilling_cached=False,
            )

    def _get_settings() -> DummySettings:
        return DummySettings()

    monkeypatch.setattr("src.api.v1.ingestion.get_settings", _get_settings)
    monkeypatch.setattr("src.api.v1.ingestion.ProfileIngestionService", DummyService)

    response = client.post("/api/v1/ingestion/res-id/10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["res_id"] == 10
    assert payload["cv_id"] == "cv-123"
    assert payload["totals"]["total"] == 6
    assert payload["availability_cached"] is True
    assert payload["reskilling_cached"] is False


def test_ingest_res_id__force_query_param__passes_to_service(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class DummySettings:
        scraper_base_url = "https://scraper"

    class DummyService:
        last_force: bool | None = None

        def ingest_res_id(self, res_id: int, *, force: bool = False) -> IngestionOutcome:
            DummyService.last_force = force
            return IngestionOutcome(
                status="success",
                res_id=res_id,
                cv_id="cv-123",
                totals=None,
                availability_cached=False,
                reskilling_cached=False,
            )

    def _get_settings() -> DummySettings:
        return DummySettings()

    monkeypatch.setattr("src.api.v1.ingestion.get_settings", _get_settings)
    monkeypatch.setattr("src.api.v1.ingestion.ProfileIngestionService", DummyService)

    response = client.post("/api/v1/ingestion/res-id/10?force=true")

    assert response.status_code == 200
    assert DummyService.last_force is True


def test_ingest_res_id__scraper_base_url_missing__returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class DummySettings:
        scraper_base_url = ""

    def _get_settings() -> DummySettings:
        return DummySettings()

    monkeypatch.setattr("src.api.v1.ingestion.get_settings", _get_settings)

    response = client.post("/api/v1/ingestion/res-id/10")

    assert response.status_code == 503
    assert response.json()["detail"] == "SCRAPER_BASE_URL not configured"


def test_ingest_res_id__invalid_res_id__returns_400(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class DummySettings:
        scraper_base_url = "https://scraper"

    class DummyService:
        def ingest_res_id(self, res_id: int, *, force: bool = False) -> IngestionOutcome:
            raise ValueError("res_id must be a positive integer")

    def _get_settings() -> DummySettings:
        return DummySettings()

    monkeypatch.setattr("src.api.v1.ingestion.get_settings", _get_settings)
    monkeypatch.setattr("src.api.v1.ingestion.ProfileIngestionService", DummyService)

    response = client.post("/api/v1/ingestion/res-id/0")

    assert response.status_code == 400
    assert response.json()["detail"] == "res_id must be a positive integer"
