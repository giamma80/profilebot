"""HTTP client for the legacy scraper service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import httpx

from src.core.config import get_settings


@dataclass(frozen=True)
class ScraperClientConfig:
    """Configuration for the scraper client."""

    base_url: str
    timeout_seconds: float = 30.0


class ScraperClient:
    """Synchronous client for the legacy scraper service."""

    def __init__(
        self,
        *,
        config: ScraperClientConfig | None = None,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        resolved_config = config or ScraperClientConfig(base_url=settings.scraper_base_url)
        base_url = resolved_config.base_url.strip()
        if not base_url:
            raise ValueError("Scraper base URL is required")
        self._config = ScraperClientConfig(
            base_url=base_url,
            timeout_seconds=resolved_config.timeout_seconds,
        )
        self._client = client or httpx.Client(
            base_url=self._config.base_url,
            timeout=self._config.timeout_seconds,
            transport=transport,
        )

    @property
    def base_url(self) -> str:
        """Return the configured base URL."""
        return self._config.base_url

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> ScraperClient:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def get(self, path: str) -> Any:
        """Perform a GET request and return JSON response."""
        return self._request("GET", path)

    def post(self, path: str, *, json: dict[str, Any] | None = None) -> Any:
        """Perform a POST request and return JSON response."""
        return self._request("POST", path, json=json)

    def fetch_inside_res_ids(self) -> list[int]:
        """Return list of res IDs from the Inside endpoint."""
        payload = self.get("/inside/res-ids")
        if isinstance(payload, dict):
            payload = payload.get("res_ids")
        if not isinstance(payload, list):
            raise ValueError("Invalid response for /inside/res-ids")
        res_ids: list[int] = []
        for value in payload:
            try:
                res_id = int(str(value).strip())
            except (TypeError, ValueError):
                continue
            if res_id:
                res_ids.append(res_id)
        return res_ids

    def refresh_inside_cv(self, res_id: int) -> None:
        """Trigger refresh for a single Inside CV."""
        self.post(f"/inside/cv/{res_id}")

    def download_inside_cv(self, res_id: int) -> bytes:
        """Download the CV DOCX bytes via GET /inside/cv/{res_id}."""
        return self._request_binary(f"/inside/cv/{res_id}")

    def export_availability_csv(self) -> None:
        """Trigger the availability CSV export."""
        self.post("/availability/csv")

    def export_reskilling_csv(self) -> None:
        """Trigger the reskilling CSV export."""
        self.post("/reskilling/csv")

    def fetch_reskilling_row(self, res_id: int) -> dict[str, Any]:
        """Return the reskilling row payload for the given res_id."""
        payload = self.get(f"/reskilling/csv/{res_id}")
        if not isinstance(payload, dict) or "row" not in payload:
            raise ValueError("Invalid response for /reskilling/csv/{res_id}")
        return payload

    def _request(self, method: str, path: str, *, json: dict[str, Any] | None = None) -> Any:
        response = self._client.request(method, path, json=json)
        response.raise_for_status()

        if not response.content:
            return None
        return response.json()

    def _request_binary(self, path: str) -> bytes:
        """GET request returning raw bytes for binary content like DOCX."""
        response = self._client.request("GET", path)
        response.raise_for_status()
        if not response.content:
            raise ValueError(f"Empty response for {path}")
        return cast(bytes, response.content)


__all__ = [
    "ScraperClient",
    "ScraperClientConfig",
]
