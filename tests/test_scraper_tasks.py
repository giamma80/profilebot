from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from celery.exceptions import MaxRetriesExceededError

from src.services.scraper import tasks as scraper_tasks
from src.services.scraper.client import ScraperClient, ScraperClientConfig


class RetryCalled(RuntimeError):
    def __init__(self, exc: Exception) -> None:
        super().__init__(str(exc))
        self.exc = exc


class DummyTask:
    def retry(self, *, exc: Exception, countdown: int) -> None:
        raise RetryCalled(exc)


@dataclass
class FakeCache:
    stored: list[int] | None = None

    def set_res_ids(self, res_ids: list[int]) -> None:
        self.stored = res_ids


def _set_base_url(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    monkeypatch.setattr(
        scraper_tasks,
        "_ensure_scraper_base_url",
        lambda: value,
        raising=True,
    )


def _mock_client(transport: httpx.MockTransport) -> ScraperClient:
    return ScraperClient(
        config=ScraperClientConfig(base_url="https://scraper"),
        transport=transport,
    )


def test_scraper_inside_refresh_task__stores_res_ids_and_returns_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_url(monkeypatch, "https://scraper")

    fake_cache = FakeCache()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/inside/res-ids":
            return httpx.Response(200, json=[10, 20])
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    monkeypatch.setattr(
        scraper_tasks,
        "ScraperResIdCache",
        lambda: fake_cache,
        raising=True,
    )
    monkeypatch.setattr(
        scraper_tasks, "ScraperClient", lambda: _mock_client(transport), raising=True
    )

    result = scraper_tasks.scraper_inside_refresh_task.run()

    assert result["status"] == "success"
    assert result["res_ids_count"] == 2
    assert result["cache_key"] == scraper_tasks.DEFAULT_RES_IDS_KEY
    assert fake_cache.stored == [10, 20]


def test_scraper_inside_refresh_task__request_error_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_url(monkeypatch, "https://scraper")

    fake_cache = FakeCache()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/inside/res-ids":
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    monkeypatch.setattr(
        scraper_tasks,
        "ScraperResIdCache",
        lambda: fake_cache,
        raising=True,
    )
    monkeypatch.setattr(
        scraper_tasks, "ScraperClient", lambda: _mock_client(transport), raising=True
    )
    monkeypatch.setattr(
        scraper_tasks.scraper_inside_refresh_task,
        "retry",
        DummyTask().retry,
        raising=True,
    )

    with pytest.raises(RetryCalled):
        scraper_tasks.scraper_inside_refresh_task.run()


def test_scraper_inside_refresh_item_task__success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_url(monkeypatch, "https://scraper")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/inside/cv/10":
            return httpx.Response(204)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    monkeypatch.setattr(
        scraper_tasks, "ScraperClient", lambda: _mock_client(transport), raising=True
    )

    result = scraper_tasks.scraper_inside_refresh_item_task.run(res_id=10)

    assert result == {"status": "success", "res_id": 10}


def test_scraper_inside_refresh_item_task__status_error_returns_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_url(monkeypatch, "https://scraper")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/inside/cv/10":
            return httpx.Response(500, request=request)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    monkeypatch.setattr(
        scraper_tasks, "ScraperClient", lambda: _mock_client(transport), raising=True
    )

    result = scraper_tasks.scraper_inside_refresh_item_task.run(res_id=10)

    assert result["status"] == "failed"
    assert result["res_id"] == 10
    assert "500" in result["reason"]


def test_scraper_inside_refresh_item_task__request_error_sends_to_dlq(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_url(monkeypatch, "https://scraper")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/inside/cv/10":
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    captured: dict[str, Any] = {}

    def _send_task(name: str, *args: Any, **options: Any) -> None:
        captured["name"] = name
        captured["kwargs"] = options.get("kwargs", {})
        captured["queue"] = options.get("queue")

    def _retry(*, exc: Exception, **_: Any) -> None:
        raise MaxRetriesExceededError()

    monkeypatch.setattr(
        scraper_tasks, "ScraperClient", lambda: _mock_client(transport), raising=True
    )
    monkeypatch.setattr(scraper_tasks.celery_app, "send_task", _send_task, raising=True)
    monkeypatch.setattr(
        scraper_tasks.scraper_inside_refresh_item_task,
        "retry",
        _retry,
        raising=True,
    )

    with pytest.raises(MaxRetriesExceededError):
        scraper_tasks.scraper_inside_refresh_item_task.run(res_id=10)

    assert captured["name"] == "scraper.refresh_inside_profile_dlq"
    assert captured["queue"] == scraper_tasks.SCRAPER_DLQ_QUEUE
    assert captured["kwargs"]["res_id"] == 10
    assert captured["kwargs"]["error_type"] == "ConnectError"
    assert "boom" in captured["kwargs"]["error"]


def test_scraper_availability_csv_refresh_task__calls_export(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_url(monkeypatch, "https://scraper")

    called: dict[str, Any] = {"availability": False}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/availability/csv":
            called["availability"] = True
            return httpx.Response(204)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    monkeypatch.setattr(
        scraper_tasks, "ScraperClient", lambda: _mock_client(transport), raising=True
    )

    result = scraper_tasks.scraper_availability_csv_refresh_task.run()

    assert result == {"status": "success"}
    assert called["availability"] is True


def test_scraper_reskilling_csv_refresh_task__returns_failed_on_status_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_url(monkeypatch, "https://scraper")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/reskilling/csv":
            return httpx.Response(400, request=request)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    monkeypatch.setattr(
        scraper_tasks, "ScraperClient", lambda: _mock_client(transport), raising=True
    )

    result = scraper_tasks.scraper_reskilling_csv_refresh_task.run()

    assert result["status"] == "failed"
    assert "400" in result["reason"]


def test_reskilling_refresh_task__no_res_ids_returns_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_url(monkeypatch, "https://scraper")

    class EmptyCache:
        def get_res_ids(self) -> list[int]:
            return []

    monkeypatch.setattr(scraper_tasks, "ScraperResIdCache", EmptyCache, raising=True)

    result = scraper_tasks.reskilling_refresh_task.run()

    assert result["status"] == "skipped"
    assert result["loaded"] == 0
    assert result["skipped"] == 0


def test_reskilling_refresh_task__refreshes_with_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_url(monkeypatch, "https://scraper")

    class FakeCache:
        def get_res_ids(self) -> list[int]:
            return [10, 20]

    class FakeService:
        def refresh(self, res_ids: list[int]) -> dict[str, int]:
            return {"total": len(res_ids), "loaded": len(res_ids), "skipped": 0}

    monkeypatch.setattr(scraper_tasks, "ScraperResIdCache", FakeCache, raising=True)
    monkeypatch.setattr(scraper_tasks, "ReskillingService", FakeService, raising=True)

    result = scraper_tasks.reskilling_refresh_task.run()

    assert result["status"] == "success"
    assert result["total_rows"] == 2
    assert result["loaded"] == 2
    assert result["skipped"] == 0
