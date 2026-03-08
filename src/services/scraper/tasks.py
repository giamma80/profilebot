"""Celery tasks for scraper ingestion refresh jobs."""

from __future__ import annotations

import logging
from typing import Any

import httpx
import redis
from celery.exceptions import MaxRetriesExceededError

from src.core.config import get_settings
from src.services.embedding.celery_app import celery_app
from src.services.reskilling.service import ReskillingService
from src.services.scraper.cache import DEFAULT_RES_IDS_KEY, ScraperResIdCache
from src.services.scraper.client import ScraperClient

logger = logging.getLogger(__name__)

RETRY_COUNTDOWN = 60
SCRAPER_DLQ_QUEUE = "scraper.dlq"


def _ensure_scraper_base_url() -> str | None:
    settings = get_settings()
    base_url = settings.scraper_base_url.strip()
    if not base_url:
        logger.warning("SCRAPER_BASE_URL not configured")
        return None
    return base_url


@celery_app.task(bind=True, max_retries=3, name="scraper.fetch_inside_res_ids")
def scraper_inside_refresh_task(self) -> dict[str, Any]:
    """Fetch Inside res IDs and store them in Redis."""
    cache = ScraperResIdCache()

    if not _ensure_scraper_base_url():
        return {"status": "skipped", "reason": "SCRAPER_BASE_URL not configured"}

    logger.info("Starting Inside res_id fetch")
    try:
        with ScraperClient() as client:
            res_ids = client.fetch_inside_res_ids()
            cache.set_res_ids(res_ids)
            logger.info("Inside res_id fetch completed with %d res_ids", len(res_ids))
            return {
                "status": "success",
                "res_ids_count": len(res_ids),
                "cache_key": DEFAULT_RES_IDS_KEY,
            }
    except httpx.RequestError as exc:
        logger.warning("Scraper Inside refresh failed: %s", exc)
        raise self.retry(exc=exc, countdown=RETRY_COUNTDOWN) from exc
    except httpx.HTTPStatusError as exc:
        logger.warning("Scraper Inside refresh failed: %s", exc)
        return {"status": "failed", "reason": str(exc)}
    except redis.RedisError as exc:
        logger.warning("Redis error during Inside refresh: %s", exc)
        raise self.retry(exc=exc, countdown=RETRY_COUNTDOWN) from exc
    except (TypeError, ValueError) as exc:
        logger.warning("Scraper Inside configuration/payload error: %s", exc)
        return {"status": "failed", "reason": str(exc)}


@celery_app.task(
    bind=True,
    max_retries=3,
    name="scraper.refresh_inside_profile",
    retry_backoff=True,
    retry_backoff_max=120,
)
def scraper_inside_refresh_item_task(self, *, res_id: int) -> dict[str, Any]:
    """Refresh a single Inside CV by res_id."""
    if not _ensure_scraper_base_url():
        return {"status": "skipped", "reason": "SCRAPER_BASE_URL not configured"}

    try:
        with ScraperClient() as client:
            client.refresh_inside_cv(res_id)
        return {"status": "success", "res_id": res_id}
    except httpx.RequestError as exc:
        logger.warning("Inside CV refresh failed for res_id %s: %s", res_id, exc)
        try:
            raise self.retry(exc=exc) from exc
        except MaxRetriesExceededError as retry_exc:
            celery_app.send_task(
                "scraper.refresh_inside_profile_dlq",
                kwargs={
                    "res_id": res_id,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
                queue=SCRAPER_DLQ_QUEUE,
            )
            logger.error("Inside CV refresh exceeded retries for res_id %s", res_id)
            raise retry_exc from exc
    except httpx.HTTPStatusError as exc:
        logger.warning("Inside CV refresh failed for res_id %s: %s", res_id, exc)
        return {"status": "failed", "reason": str(exc), "res_id": res_id}
    except (TypeError, ValueError) as exc:
        logger.warning("Inside CV refresh failed for res_id %s: %s", res_id, exc)
        return {"status": "failed", "reason": str(exc), "res_id": res_id}


@celery_app.task(name="scraper.refresh_inside_profile_dlq")
def scraper_inside_refresh_dlq_task(*, res_id: int, error: str, error_type: str) -> dict[str, Any]:
    """Record Inside CV refresh failures that exceeded retries."""
    logger.error(
        "Inside CV refresh sent to DLQ: res_id=%s error_type=%s error=%s",
        res_id,
        error_type,
        error,
    )
    return {"status": "dlq", "res_id": res_id, "error": error, "error_type": error_type}


@celery_app.task(bind=True, max_retries=3, name="scraper.export_availability_csv")
def scraper_availability_csv_refresh_task(self) -> dict[str, Any]:
    """Trigger the availability CSV export."""
    if not _ensure_scraper_base_url():
        return {"status": "skipped", "reason": "SCRAPER_BASE_URL not configured"}

    try:
        with ScraperClient() as client:
            client.export_availability_csv()
        return {"status": "success"}
    except httpx.RequestError as exc:
        logger.warning("Scraper availability export failed: %s", exc)
        raise self.retry(exc=exc, countdown=RETRY_COUNTDOWN) from exc
    except httpx.HTTPStatusError as exc:
        logger.warning("Scraper availability export failed: %s", exc)
        return {"status": "failed", "reason": str(exc)}


@celery_app.task(bind=True, max_retries=3, name="scraper.export_reskilling_csv")
def scraper_reskilling_csv_refresh_task(self) -> dict[str, Any]:
    """Trigger the reskilling CSV export."""
    if not _ensure_scraper_base_url():
        return {"status": "skipped", "reason": "SCRAPER_BASE_URL not configured"}

    try:
        with ScraperClient() as client:
            client.export_reskilling_csv()
        return {"status": "success"}
    except httpx.RequestError as exc:
        logger.warning("Scraper reskilling export failed: %s", exc)
        raise self.retry(exc=exc, countdown=RETRY_COUNTDOWN) from exc
    except httpx.HTTPStatusError as exc:
        logger.warning("Scraper reskilling export failed: %s", exc)
        return {"status": "failed", "reason": str(exc)}


@celery_app.task(bind=True, max_retries=3, name="scraper.refresh_reskilling_cache")
def reskilling_refresh_task(self) -> dict[str, Any]:
    """Refresh reskilling cache from the scraper service."""
    if not _ensure_scraper_base_url():
        return {
            "status": "skipped",
            "reason": "SCRAPER_BASE_URL not configured",
            "total_rows": 0,
            "loaded": 0,
            "skipped": 0,
        }

    cache = ScraperResIdCache()
    try:
        res_ids = cache.get_res_ids()
    except (TypeError, ValueError) as exc:
        logger.warning("Reskilling refresh failed: %s", exc)
        return {
            "status": "failed",
            "reason": str(exc),
            "total_rows": 0,
            "loaded": 0,
            "skipped": 0,
        }

    if not res_ids:
        return {
            "status": "skipped",
            "reason": "no res_ids in cache",
            "total_rows": 0,
            "loaded": 0,
            "skipped": 0,
        }

    service = ReskillingService()
    try:
        result = service.refresh(res_ids)
        return {
            "status": "success",
            "total_rows": result["total"],
            "loaded": result["loaded"],
            "skipped": result["skipped"],
        }
    except httpx.RequestError as exc:
        logger.warning("Reskilling refresh failed: %s", exc)
        raise self.retry(exc=exc, countdown=RETRY_COUNTDOWN) from exc
    except httpx.HTTPStatusError as exc:
        logger.warning("Reskilling refresh failed: %s", exc)
        return {
            "status": "failed",
            "reason": str(exc),
            "total_rows": 0,
            "loaded": 0,
            "skipped": 0,
        }
    except redis.RedisError as exc:
        logger.warning("Redis error during reskilling refresh: %s", exc)
        raise self.retry(exc=exc, countdown=RETRY_COUNTDOWN) from exc
    except (TypeError, ValueError) as exc:
        logger.warning("Reskilling refresh failed: %s", exc)
        return {
            "status": "failed",
            "reason": str(exc),
            "total_rows": 0,
            "loaded": 0,
            "skipped": 0,
        }
