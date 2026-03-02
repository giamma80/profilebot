"""Celery tasks for availability refresh jobs."""

from __future__ import annotations

import logging
from typing import Any

import httpx
import redis

from src.core.config import get_settings
from src.services.embedding.celery_app import celery_app
from src.services.scraper.client import ScraperClient

logger = logging.getLogger(__name__)

RETRY_COUNTDOWN = 60


@celery_app.task(bind=True, max_retries=3, name="availability.refresh")
def availability_refresh_task(self) -> dict[str, Any]:
    """Refresh availability cache via scraper service.

    Flow:
        1. Call ScraperClient.export_availability_csv() to trigger CSV export
        2. Fetch the exported data via ScraperClient
        3. Load records into Redis cache

    Returns:
        Summary with status, loaded records, and any errors.
    """
    settings = get_settings()
    base_url = settings.scraper_base_url.strip()
    if not base_url:
        logger.warning("SCRAPER_BASE_URL not configured, skipping availability refresh")
        return {"status": "skipped", "reason": "SCRAPER_BASE_URL not configured"}

    try:
        with ScraperClient() as client:
            client.export_availability_csv()
        logger.info("Availability CSV export triggered via scraper service")
        return {"status": "success"}
    except httpx.RequestError as exc:
        logger.warning("Availability refresh failed (transient): %s", exc)
        raise self.retry(exc=exc, countdown=RETRY_COUNTDOWN) from exc
    except httpx.HTTPStatusError as exc:
        logger.warning("Availability refresh failed (HTTP %s): %s", exc.response.status_code, exc)
        return {"status": "failed", "reason": str(exc)}
    except redis.RedisError as exc:
        logger.warning("Redis error during availability refresh: %s", exc)
        raise self.retry(exc=exc, countdown=RETRY_COUNTDOWN) from exc
