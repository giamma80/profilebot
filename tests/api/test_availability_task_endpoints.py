from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_availability_refresh__queues_task__returns_accepted(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    task_ids: list[str] = []

    class DummyTask:
        def __init__(self, task_id: str) -> None:
            self.id = task_id

    def _delay() -> DummyTask:
        task_id = "task-default"
        task_ids.append(task_id)
        return DummyTask(task_id)

    monkeypatch.setattr("src.api.v1.availability.availability_refresh_task.delay", _delay)

    response = client.post("/api/v1/availability/refresh")

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["task_id"].startswith("task-")
    assert task_ids


def test_availability_refresh_status__returns_result_when_ready(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class DummyResult:
        def __init__(self) -> None:
            self.status = "SUCCESS"
            self.result = {"status": "success", "loaded": 2}
            self.traceback = None

        def ready(self) -> bool:
            return True

        def failed(self) -> bool:
            return False

    def _async_result(task_id: str, *, app: Any) -> DummyResult:
        return DummyResult()

    monkeypatch.setattr("src.api.v1.availability.AsyncResult", _async_result)

    response = client.get("/api/v1/availability/refresh/task-123")

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == "task-123"
    assert payload["status"] == "SUCCESS"
    assert payload["result"] == {"status": "success", "loaded": 2}
    assert payload["traceback"] is None


def test_availability_refresh_status__returns_traceback_on_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class DummyResult:
        def __init__(self) -> None:
            self.status = "FAILURE"
            self.result = None
            self.traceback = "boom"

        def ready(self) -> bool:
            return True

        def failed(self) -> bool:
            return True

    def _async_result(task_id: str, *, app: Any) -> DummyResult:
        return DummyResult()

    monkeypatch.setattr("src.api.v1.availability.AsyncResult", _async_result)

    response = client.get("/api/v1/availability/refresh/task-fail")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "FAILURE"
    assert payload["result"] is None
    assert payload["traceback"] == "boom"


def test_availability_tasks__returns_inspection_payload(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class DummyInspect:
        def active(self) -> dict[str, Any]:
            return {"worker-1": []}

        def reserved(self) -> dict[str, Any]:
            return {"worker-1": []}

        def scheduled(self) -> dict[str, Any]:
            return {"worker-1": []}

    def _inspect() -> DummyInspect:
        return DummyInspect()

    monkeypatch.setattr("src.api.v1.availability.celery_app.control.inspect", _inspect)

    response = client.get("/api/v1/availability/tasks")

    assert response.status_code == 200
    payload = response.json()
    assert payload["active"] == {"worker-1": []}
    assert payload["reserved"] == {"worker-1": []}
    assert payload["scheduled"] == {"worker-1": []}
