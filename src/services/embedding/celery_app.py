"""Celery application configuration for ProfileBot embedding tasks."""

from __future__ import annotations

from celery import Celery

from src.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "profilebot",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["src.services.embedding.tasks"],
)

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
)

__all__ = ["celery_app"]
