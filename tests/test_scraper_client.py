from __future__ import annotations

from typing import Any

import httpx
import pytest

from src.services.scraper.client import ScraperClient, ScraperClientConfig


def test_fetch_inside_res_ids__valid_payload__returns_normalized_ids() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/inside/res-ids"
        return httpx.Response(200, json=["1", 2, " ", None, "003"])

    transport = httpx.MockTransport(handler)
    client = ScraperClient(
        config=ScraperClientConfig(base_url="https://scraper"),
        transport=transport,
    )

    with client:
        result = client.fetch_inside_res_ids()

    assert result == [1, 2, 3]


def test_fetch_inside_res_ids__object_payload__returns_normalized_ids() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/inside/res-ids"
        return httpx.Response(200, json={"res_ids": ["10", "020", None, ""]})

    transport = httpx.MockTransport(handler)
    client = ScraperClient(
        config=ScraperClientConfig(base_url="https://scraper"),
        transport=transport,
    )

    with client:
        result = client.fetch_inside_res_ids()

    assert result == [10, 20]


def test_fetch_inside_res_ids__invalid_payload__raises_value_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"res_ids": "invalid"})

    transport = httpx.MockTransport(handler)
    client = ScraperClient(
        config=ScraperClientConfig(base_url="https://scraper"),
        transport=transport,
    )

    with pytest.raises(ValueError, match="Invalid response for /inside/res-ids"):
        with client:
            client.fetch_inside_res_ids()


def test_refresh_inside_cv__posts_to_expected_path() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        return httpx.Response(204)

    transport = httpx.MockTransport(handler)
    client = ScraperClient(
        config=ScraperClientConfig(base_url="https://scraper"),
        transport=transport,
    )

    with client:
        client.refresh_inside_cv(123)

    assert captured["method"] == "POST"
    assert captured["path"] == "/inside/cv/123"


def test_export_availability_csv__posts_to_expected_path() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        return httpx.Response(204)

    transport = httpx.MockTransport(handler)
    client = ScraperClient(
        config=ScraperClientConfig(base_url="https://scraper"),
        transport=transport,
    )

    with client:
        client.export_availability_csv()

    assert captured["method"] == "POST"
    assert captured["path"] == "/availability/csv"


def test_export_reskilling_csv__posts_to_expected_path() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        return httpx.Response(204)

    transport = httpx.MockTransport(handler)
    client = ScraperClient(
        config=ScraperClientConfig(base_url="https://scraper"),
        transport=transport,
    )

    with client:
        client.export_reskilling_csv()

    assert captured["method"] == "POST"
    assert captured["path"] == "/reskilling/csv"


def test_fetch_reskilling_row__returns_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/reskilling/csv/123"
        return httpx.Response(
            200,
            json={
                "res_id": "123",
                "row": {"Risorsa:Consultant ID": "123"},
            },
        )

    transport = httpx.MockTransport(handler)
    client = ScraperClient(
        config=ScraperClientConfig(base_url="https://scraper"),
        transport=transport,
    )

    with client:
        payload = client.fetch_reskilling_row(123)

    assert payload["res_id"] == "123"
    assert payload["row"]["Risorsa:Consultant ID"] == "123"


def test_fetch_reskilling_row__invalid_payload__raises_value_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"res_id": "123"})

    transport = httpx.MockTransport(handler)
    client = ScraperClient(
        config=ScraperClientConfig(base_url="https://scraper"),
        transport=transport,
    )

    with pytest.raises(ValueError, match=r"Invalid response for /reskilling/csv/{res_id}"):
        with client:
            client.fetch_reskilling_row(123)


def test_request_error__propagates_httpx_request_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    transport = httpx.MockTransport(handler)
    client = ScraperClient(
        config=ScraperClientConfig(base_url="https://scraper"),
        transport=transport,
    )

    with pytest.raises(httpx.RequestError):
        with client:
            client.fetch_inside_res_ids()


def test_http_status_error__propagates_httpx_status_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, request=request)

    transport = httpx.MockTransport(handler)
    client = ScraperClient(
        config=ScraperClientConfig(base_url="https://scraper"),
        transport=transport,
    )

    with pytest.raises(httpx.HTTPStatusError):
        with client:
            client.export_availability_csv()
