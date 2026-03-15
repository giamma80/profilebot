from __future__ import annotations

import httpx
import pytest

from src.services.ingestion import tasks as ingestion_tasks


class RetryCalled(RuntimeError):
    def __init__(self, exc: Exception) -> None:
        super().__init__(str(exc))
        self.exc = exc


class DummyTask:
    def retry(self, *, exc: Exception, countdown: int) -> None:
        raise RetryCalled(exc)


class DummyClient:
    def __enter__(self) -> DummyClient:
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        return None

    def post(self, url: str) -> httpx.Response:
        request = httpx.Request("POST", url)
        raise httpx.ConnectError("boom", request=request)


def test_ingestion_process_res_id_task__success(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/v1/ingestion/res-id/10":
            return httpx.Response(200, json={"status": "success"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    original_client = httpx.Client

    monkeypatch.setattr(ingestion_tasks, "_ensure_ingestion_base_url", lambda: "https://api")
    monkeypatch.setattr(
        ingestion_tasks.httpx,
        "Client",
        lambda **_: original_client(transport=transport),
        raising=True,
    )

    result = ingestion_tasks.ingestion_process_res_id_task.run(res_id=10)

    assert result["status"] == "success"
    assert result["res_id"] == 10
    assert result["response"] == {"status": "success"}


def test_ingestion_process_res_id_task__missing_base_url_skips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ingestion_tasks, "_ensure_ingestion_base_url", lambda: None)

    result = ingestion_tasks.ingestion_process_res_id_task.run(res_id=10)

    assert result["status"] == "skipped"
    assert result["reason"] == "INGESTION_API_BASE_URL not configured"


def test_ingestion_process_res_id_task__request_error_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ingestion_tasks, "_ensure_ingestion_base_url", lambda: "https://api")
    monkeypatch.setattr(ingestion_tasks.httpx, "Client", lambda **_: DummyClient(), raising=True)
    monkeypatch.setattr(
        ingestion_tasks.ingestion_process_res_id_task,
        "retry",
        DummyTask().retry,
        raising=True,
    )

    with pytest.raises(RetryCalled):
        ingestion_tasks.ingestion_process_res_id_task.run(res_id=10)
