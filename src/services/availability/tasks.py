"""Celery tasks for availability refresh jobs."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import redis

from src.core.config import get_settings
from src.services.availability.loader import load_from_csv
from src.services.embedding.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def availability_refresh_task(
    self,
    *,
    csv_path: str | None = None,
) -> dict[str, Any]:
    """Refresh availability cache from a canonical CSV file.

    Args:
        csv_path: Optional CSV path. If not provided, uses settings.

    Returns:
        Summary with total rows, loaded records, and skipped rows.
    """
    settings = get_settings()
    resolved_path = csv_path or settings.availability_refresh_csv_path
    if not resolved_path:
        return {
            "status": "skipped",
            "reason": "availability_refresh_csv_path not configured",
            "total_rows": 0,
            "loaded": 0,
            "skipped": 0,
        }

    path = Path(resolved_path)
    if not path.exists():
        return {
            "status": "failed",
            "reason": f"CSV not found: {path}",
            "total_rows": 0,
            "loaded": 0,
            "skipped": 0,
        }

    try:
        result = load_from_csv(path)
        return {
            "status": "success",
            "total_rows": result.total_rows,
            "loaded": result.loaded,
            "skipped": result.skipped,
            "csv_path": str(path),
        }
    except (ValueError, FileNotFoundError) as exc:
        logger.warning("Availability refresh failed: %s", exc)
        return {
            "status": "failed",
            "reason": str(exc),
            "total_rows": 0,
            "loaded": 0,
            "skipped": 0,
            "csv_path": str(path),
        }
    except redis.RedisError as exc:
        logger.warning("Redis error during availability refresh: %s", exc)
        raise self.retry(exc=exc, countdown=60) from exc
