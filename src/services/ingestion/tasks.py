"""Celery tasks for ingestion API calls."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

import httpx
import redis
from celery.exceptions import MaxRetriesExceededError

from src.core.config import get_settings
from src.services.embedding.celery_app import celery_app

logger = logging.getLogger(__name__)

RETRY_COUNTDOWN = 60
SERVER_ERROR_STATUS_CODE = 500
INGESTION_DLQ_QUEUE = "ingestion.dlq"
PIPELINE_FAILED_COUNT_KEY = "pipeline:failed_count"
PIPELINE_LAST_RUN_AT_KEY = "pipeline:last_run_at"


def _log_ingestion_complete(
    *,
    res_id: int,
    start_time: float,
    status: str,
    error_type: str | None,
) -> None:
    duration_ms = int((time.perf_counter() - start_time) * 1000)
    logger.info(
        "ingestion.complete",
        extra={
            "res_id": res_id,
            "duration_ms": duration_ms,
            "status": status,
            "error_type": error_type,
        },
    )


def _ensure_ingestion_base_url() -> str | None:
    settings = get_settings()
    base_url = settings.ingestion_api_base_url.strip().rstrip("/")
    if not base_url:
        logger.warning("INGESTION_API_BASE_URL not configured")
        return None
    return base_url


def _get_pipeline_redis_client() -> redis.Redis | None:
    settings = get_settings()
    try:
        return redis.from_url(settings.celery_result_backend, decode_responses=True)
    except (redis.RedisError, ValueError) as exc:
        logger.warning("Pipeline metadata Redis unavailable: %s", exc)
        return None


def _record_pipeline_run(*, success: bool) -> None:
    client = _get_pipeline_redis_client()
    if client is None:
        return
    try:
        now = datetime.now(UTC).isoformat()
        client.set(PIPELINE_LAST_RUN_AT_KEY, now)
        if not success:
            client.incr(PIPELINE_FAILED_COUNT_KEY)
    except redis.RedisError as exc:
        logger.warning("Failed to update pipeline metadata: %s", exc)


@celery_app.task(
    bind=True,
    max_retries=3,
    name="ingestion.process_res_id",
    retry_backoff=True,
    retry_backoff_max=120,
)
def ingestion_process_res_id_task(self, *, res_id: int, force: bool = False) -> dict[str, Any]:
    """Call the ingestion API for a single res_id."""
    start_time = time.perf_counter()
    if not res_id:
        _log_ingestion_complete(
            res_id=res_id,
            start_time=start_time,
            status="skipped",
            error_type="missing_res_id",
        )
        return {"status": "skipped", "reason": "missing res_id", "res_id": res_id}

    settings = get_settings()
    base_url = _ensure_ingestion_base_url()
    if not base_url:
        _log_ingestion_complete(
            res_id=res_id,
            start_time=start_time,
            status="skipped",
            error_type="config_missing",
        )
        return {
            "status": "skipped",
            "reason": "INGESTION_API_BASE_URL not configured",
            "res_id": res_id,
        }

    url = f"{base_url}/api/v1/ingestion/res-id/{res_id}"
    params = {"force": "true"} if force else None
    try:
        with httpx.Client(timeout=settings.ingestion_api_timeout) as client:
            response = client.post(url, params=params)
            response.raise_for_status()
            payload: dict[str, Any] | None = None
            if response.content:
                payload = response.json()
        _record_pipeline_run(success=True)
        _log_ingestion_complete(
            res_id=res_id,
            start_time=start_time,
            status="success",
            error_type=None,
        )
        return {"status": "success", "res_id": res_id, "response": payload}
    except httpx.RequestError as exc:
        logger.warning("Ingestion API request failed for res_id %s: %s", res_id, exc)
        _log_ingestion_complete(
            res_id=res_id,
            start_time=start_time,
            status="retrying",
            error_type=type(exc).__name__,
        )
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
            _record_pipeline_run(success=False)
            _log_ingestion_complete(
                res_id=res_id,
                start_time=start_time,
                status="dlq",
                error_type=type(exc).__name__,
            )
            raise retry_exc from exc
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        logger.warning("Ingestion API HTTP error for res_id %s: %s", res_id, exc)
        if status_code is not None and status_code >= SERVER_ERROR_STATUS_CODE:
            _log_ingestion_complete(
                res_id=res_id,
                start_time=start_time,
                status="retrying",
                error_type=type(exc).__name__,
            )
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
                _record_pipeline_run(success=False)
                _log_ingestion_complete(
                    res_id=res_id,
                    start_time=start_time,
                    status="dlq",
                    error_type=type(exc).__name__,
                )
                raise retry_exc from exc
        _record_pipeline_run(success=False)
        _log_ingestion_complete(
            res_id=res_id,
            start_time=start_time,
            status="failed",
            error_type=type(exc).__name__,
        )
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
