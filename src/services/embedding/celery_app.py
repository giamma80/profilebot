"""Celery application configuration for ProfileBot embedding tasks."""

from __future__ import annotations

import logging

from celery import Celery
from celery.schedules import crontab

from src.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

celery_app = Celery(
    "profilebot",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "src.services.embedding.tasks",
        "src.services.availability.tasks",
    ],
)

CRON_FIELDS = 5


def _parse_cron_schedule(value: str):
    parts = value.split()
    if len(parts) != CRON_FIELDS:
        logger.warning("Invalid availability cron '%s', defaulting to hourly", value)
        return crontab(minute=0)
    return crontab(*parts)


celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.celery_task_time_limit,
    result_expires=settings.celery_result_expires,
    worker_prefetch_multiplier=4,
    worker_concurrency=settings.celery_worker_concurrency,
    beat_schedule={
        "availability-refresh": {
            "task": "src.services.availability.tasks.availability_refresh_task",
            "schedule": _parse_cron_schedule(settings.availability_refresh_schedule),
        }
    },
)

__all__ = ["celery_app"]
