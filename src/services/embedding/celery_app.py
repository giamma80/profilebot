"""Celery application configuration for ProfileBot embedding tasks."""

from __future__ import annotations

import logging
import resource
import tracemalloc
from itertools import count
from pathlib import Path

from celery import Celery, signals
from celery.schedules import crontab

from src.core.config import get_settings
from src.core.workflows.loader import load_workflow

logger = logging.getLogger(__name__)
settings = get_settings()

MEMORY_PROBE_INTERVAL = max(1, settings.memory_probe_log_every)
_task_counter = count(1)

if settings.memory_probe_enabled:
    tracemalloc.start()

    @signals.task_postrun.connect
    def _log_task_memory(sender: object | None = None, **_kwargs: object) -> None:
        task_count = next(_task_counter)
        if task_count % MEMORY_PROBE_INTERVAL != 0:
            return
        current, peak = tracemalloc.get_traced_memory()
        rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        task_name = getattr(sender, "name", None)
        logger.info(
            "memory_probe tasks=%s task=%s current_bytes=%s peak_bytes=%s rss_kb=%s",
            task_count,
            task_name,
            current,
            peak,
            rss_kb,
        )


celery_app = Celery(
    "profilebot",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "src.services.embedding.tasks",
        "src.services.availability.tasks",
        "src.services.scraper.tasks",
        "src.services.ingestion.tasks",
        "src.services.workflows.tasks",
    ],
)

CRON_FIELDS = 5
DEFAULT_AVAILABILITY_SCHEDULE = crontab(minute=0)
DEFAULT_RESKILLING_SCHEDULE = crontab(minute="*/30")
DEFAULT_SCRAPER_SCHEDULE = crontab(minute=0, hour="*/4")
SCRAPER_WORKFLOW_TASK = "workflow.run_ingestion"


def _parse_cron_schedule(value: str, *, default: crontab) -> crontab:
    parts = value.split()
    if len(parts) != CRON_FIELDS:
        logger.warning("Invalid cron %s, defaulting to %s", value, default)
        return default
    return crontab(*parts)


def _resolve_scraper_schedule() -> crontab:
    path = Path(settings.scraper_workflow_path)
    try:
        definition = load_workflow(path)
    except FileNotFoundError:
        logger.warning("Scraper workflow file not found: %s", path)
        return DEFAULT_SCRAPER_SCHEDULE
    except ValueError as exc:
        logger.warning("Invalid scraper workflow file %s: %s", path, exc)
        return DEFAULT_SCRAPER_SCHEDULE
    if not definition.schedule:
        return DEFAULT_SCRAPER_SCHEDULE
    return _parse_cron_schedule(definition.schedule, default=DEFAULT_SCRAPER_SCHEDULE)


celery_config = {
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
    "task_track_started": True,
    "task_time_limit": settings.celery_task_time_limit,
    "result_expires": settings.celery_result_expires,
    "worker_prefetch_multiplier": settings.celery_worker_prefetch_multiplier,
    "worker_concurrency": settings.celery_worker_concurrency,
    "task_acks_late": settings.celery_task_acks_late,
    "beat_schedule": {
        "availability-refresh": {
            "task": "availability.refresh_cache",
            "schedule": _parse_cron_schedule(
                settings.availability_refresh_schedule,
                default=DEFAULT_AVAILABILITY_SCHEDULE,
            ),
        },
        "reskilling-refresh": {
            "task": "scraper.refresh_reskilling_cache",
            "schedule": _parse_cron_schedule(
                settings.reskilling_refresh_schedule,
                default=DEFAULT_RESKILLING_SCHEDULE,
            ),
        },
        "scraper-workflow": {
            "task": SCRAPER_WORKFLOW_TASK,
            "schedule": _resolve_scraper_schedule(),
        },
    },
}

if settings.celery_worker_max_tasks_per_child is not None:
    celery_config["worker_max_tasks_per_child"] = settings.celery_worker_max_tasks_per_child
if settings.celery_worker_max_memory_per_child_kb is not None:
    celery_config["worker_max_memory_per_child"] = settings.celery_worker_max_memory_per_child_kb

celery_app.conf.update(celery_config)

__all__ = ["celery_app"]
