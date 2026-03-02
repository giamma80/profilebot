"""Celery tasks for workflow orchestration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from celery import group, signature

from src.core.config import get_settings
from src.core.workflows.loader import load_workflow
from src.core.workflows.runner import WorkflowRunner
from src.services.embedding.celery_app import celery_app
from src.services.scraper.cache import ScraperResIdCache

logger = logging.getLogger(__name__)


@celery_app.task(name="workflow.run_scraper")
def run_scraper_workflow_task(*, workflow_path: str | None = None) -> dict[str, Any]:
    """Trigger the scraper ingestion workflow."""
    settings = get_settings()
    resolved_path = Path(workflow_path or settings.scraper_workflow_path)
    definition = load_workflow(resolved_path)
    runner = WorkflowRunner(app=celery_app)
    result = runner.run(definition)
    logger.info(
        "Triggered workflow %s with root task %s",
        definition.workflow_id,
        result.id,
    )
    return {
        "status": "triggered",
        "workflow_id": definition.workflow_id,
        "root_task_id": result.id,
        "node_count": len(definition.nodes),
    }


@celery_app.task(name="workflow.fanout")
def run_workflow_fanout_task(
    _results: list[Any] | None = None,
    *,
    fanout_source: str,
    fanout_task: str,
    fanout_parameter_name: str = "res_id",
) -> dict[str, Any]:
    """Trigger a fan-out based on a cached res_id list."""
    res_ids = _load_fanout_res_ids(fanout_source)
    if not res_ids:
        logger.info("Fanout skipped, no res_ids found for %s", fanout_source)
        return {"status": "skipped", "res_ids_count": 0}

    signatures = [
        signature(fanout_task, kwargs={fanout_parameter_name: res_id}) for res_id in res_ids
    ]
    result = group(signatures).apply_async()
    child_ids = [child.id for child in (result.children or [])]

    logger.info(
        "Triggered fanout for %d res_ids with group %s",
        len(res_ids),
        result.id,
    )
    return {
        "status": "triggered",
        "res_ids_count": len(res_ids),
        "group_id": result.id,
        "child_task_ids": child_ids,
    }


def _load_fanout_res_ids(fanout_source: str) -> list[int]:
    if not fanout_source.startswith("redis:"):
        raise ValueError(f"Unsupported fanout source: {fanout_source}")
    key = fanout_source.replace("redis:", "", 1)
    if not key:
        raise ValueError("Fanout source key is required")
    cache = ScraperResIdCache(key=key)
    return cache.get_res_ids()
