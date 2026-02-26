from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import pytest

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
    refreshed: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/inside/res-ids":
            return httpx.Response(200, json=[10, 20])
        if request.method == "POST" and request.url.path.startswith("/inside/cv/"):
            refreshed.append(int(request.url.path.split("/")[-1]))
            return httpx.Response(204)
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
    assert result["failed_res_ids"] == []
    assert result["cache_key"] == scraper_tasks.DEFAULT_RES_IDS_KEY
    assert fake_cache.stored == [10, 20]
    assert refreshed == [10, 20]


def test_scraper_inside_refresh_task__request_error_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_base_url(monkeypatch, "https://scraper")

    fake_cache = FakeCache()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/inside/res-ids":
            return httpx.Response(200, json=[10])
        if request.method == "POST" and request.url.path == "/inside/cv/10":
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
