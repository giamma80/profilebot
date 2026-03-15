"""Celery tasks for ingestion API calls."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from celery.exceptions import MaxRetriesExceededError

from src.core.config import get_settings
from src.services.embedding.celery_app import celery_app

logger = logging.getLogger(__name__)

RETRY_COUNTDOWN = 60
SERVER_ERROR_STATUS_CODE = 500
INGESTION_DLQ_QUEUE = "ingestion.dlq"


def _ensure_ingestion_base_url() -> str | None:
    settings = get_settings()
    base_url = settings.ingestion_api_base_url.strip().rstrip("/")
    if not base_url:
        logger.warning("INGESTION_API_BASE_URL not configured")
        return None
    return base_url


@celery_app.task(
    bind=True,
    max_retries=3,
    name="ingestion.process_res_id",
    retry_backoff=True,
    retry_backoff_max=120,
)
def ingestion_process_res_id_task(self, *, res_id: int) -> dict[str, Any]:
    """Call the ingestion API for a single res_id."""
    if not res_id:
        return {"status": "skipped", "reason": "missing res_id", "res_id": res_id}

    base_url = _ensure_ingestion_base_url()
    if not base_url:
        return {
            "status": "skipped",
            "reason": "INGESTION_API_BASE_URL not configured",
            "res_id": res_id,
        }

    url = f"{base_url}/api/v1/ingestion/res-id/{res_id}"
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url)
            response.raise_for_status()
            payload: dict[str, Any] | None = None
            if response.content:
                payload = response.json()
        return {"status": "success", "res_id": res_id, "response": payload}
    except httpx.RequestError as exc:
        logger.warning("Ingestion API request failed for res_id %s: %s", res_id, exc)
        try:
            raise self.retry(exc=exc, countdown=RETRY_COUNTDOWN) from exc
        except MaxRetriesExceededError as retry_exc:
            celery_app.send_task(
                "ingestion.process_res_id_dlq",
                kwargs={
                    "res_id": res_id,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
                queue=INGESTION_DLQ_QUEUE,
            )
            logger.error("Ingestion API exceeded retries for res_id %s", res_id)
            raise retry_exc from exc
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        logger.warning("Ingestion API HTTP error for res_id %s: %s", res_id, exc)
        if status_code is not None and status_code >= SERVER_ERROR_STATUS_CODE:
            try:
                raise self.retry(exc=exc, countdown=RETRY_COUNTDOWN) from exc
            except MaxRetriesExceededError as retry_exc:
                celery_app.send_task(
                    "ingestion.process_res_id_dlq",
                    kwargs={
                        "res_id": res_id,
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    },
                    queue=INGESTION_DLQ_QUEUE,
                )
                logger.error("Ingestion API exceeded retries for res_id %s", res_id)
                raise retry_exc from exc
        return {
            "status": "failed",
            "res_id": res_id,
            "error": str(exc),
            "error_type": type(exc).__name__,
        }


@celery_app.task(name="ingestion.process_res_id_dlq")
def ingestion_process_res_id_dlq_task(
    *, res_id: int, error: str, error_type: str
) -> dict[str, Any]:
    """Record ingestion failures that exceeded retries."""
    logger.error(
        "Ingestion API sent to DLQ: res_id=%s error_type=%s error=%s",
        res_id,
        error_type,
        error,
    )
    return {"status": "dlq", "res_id": res_id, "error": error, "error_type": error_type}
