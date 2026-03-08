"""Celery tasks for workflow orchestration."""

from __future__ import annotations

import logging
import time
from math import ceil
from pathlib import Path
from typing import Any

from celery import group, signature
from celery.result import AsyncResult, GroupResult, allow_join_result

from src.core.config import get_settings
from src.core.workflows.loader import load_workflow
from src.core.workflows.patterns import BestEffortChord
from src.core.workflows.runner import WorkflowRunner
from src.services.embedding.celery_app import celery_app
from src.services.scraper.cache import ScraperResIdCache
from src.utils.metrics import CHORD_PARTIAL_FAILURES

logger = logging.getLogger(__name__)


@celery_app.task(name="workflow.run_ingestion")
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


@celery_app.task(name="workflow.fanout_by_res_id")
def run_workflow_fanout_task(
    *_args: Any,
    fanout_source: str,
    fanout_task: str,
    fanout_parameter_name: str = "res_id",
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Trigger a fan-out based on a cached res_id list."""
    res_ids = _load_fanout_res_ids(fanout_source)
    if not res_ids:
        logger.info("Fanout skipped, no res_ids found for %s", fanout_source)
        return {"status": "skipped", "res_ids_count": 0}

    options = options or {}
    callback_task = options.get("callback_task")
    on_error_task = options.get("on_error_task")
    min_success_ratio = options.get("min_success_ratio", 0.8)

    signatures = [
        signature(fanout_task, kwargs={fanout_parameter_name: res_id}) for res_id in res_ids
    ]

    if callback_task is not None:
        callback_signature = signature(callback_task, kwargs={})
        on_error_signature = None
        if on_error_task is not None:
            on_error_signature = signature(on_error_task, kwargs={})
        builder = BestEffortChord(app=celery_app, min_success_ratio=min_success_ratio)
        chord_signature = builder.build(
            signatures,
            callback_signature,
            on_error=on_error_signature,
        )
        result = chord_signature.apply_async()
        logger.info(
            "Triggered best-effort fanout for %d res_ids with chord %s",
            len(res_ids),
            result.id,
        )
        return {
            "status": "triggered",
            "res_ids_count": len(res_ids),
            "chord_task_id": result.id,
        }

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


@celery_app.task(name="workflow.log_failed_profiles")
def log_failed_profiles_task(
    _results: list[Any] | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Log failed profile refreshes for retry follow-up."""
    if not errors:
        logger.info("No failed profiles to log")
        return {"status": "empty", "failed_count": 0, "failed_res_ids": []}

    failed_res_ids: list[int] = []
    for error in errors:
        res_id = error.get("res_id") if isinstance(error, dict) else None
        error_type = error.get("error_type") if isinstance(error, dict) else None
        message = error.get("error") if isinstance(error, dict) else None
        logger.warning(
            "Profile refresh failed: res_id=%s error_type=%s error=%s",
            res_id,
            error_type,
            message,
        )
        if isinstance(res_id, int):
            failed_res_ids.append(res_id)

    return {
        "status": "logged",
        "failed_count": len(failed_res_ids),
        "failed_res_ids": failed_res_ids,
    }


@celery_app.task(bind=True, max_retries=10, name="workflow.best_effort_group")
def best_effort_chord_task(self, payload: dict[str, Any]) -> dict[str, Any]:
    """Trigger a best-effort chord that tolerates partial failures."""
    header = payload["header"]
    body = payload["body"]
    min_success_ratio = payload.get("min_success_ratio", 0.8)
    poll_interval = payload.get("poll_interval", 5)
    max_wait_seconds = payload.get("max_wait_seconds")
    task_metadata = payload.get("task_metadata")
    on_error = payload.get("on_error")
    group_id = payload.get("group_id")
    child_ids = payload.get("child_ids")
    started_at = payload.get("started_at")

    if max_wait_seconds is None:
        settings = get_settings()
        max_wait_seconds = settings.best_effort_chord_max_wait_seconds

    payload = {
        **payload,
        "body": body,
        "child_ids": child_ids,
        "group_id": group_id,
        "header": header,
        "max_wait_seconds": max_wait_seconds,
        "min_success_ratio": min_success_ratio,
        "on_error": on_error,
        "poll_interval": poll_interval,
        "started_at": started_at,
        "task_metadata": task_metadata,
    }

    if group_id is None:
        signatures = [_coerce_signature(sig) for sig in header]
        result = group(signatures).apply_async()
        child_ids = [child.id for child in (result.children or [])]
        result.save()
        if started_at is None:
            started_at = time.time()
        max_retries = _compute_max_retries(max_wait_seconds, poll_interval)
        raise self.retry(
            countdown=poll_interval,
            max_retries=max_retries,
            kwargs={
                "payload": {
                    **payload,
                    "group_id": result.id,
                    "child_ids": child_ids,
                    "started_at": started_at,
                }
            },
        )

    group_result = GroupResult.restore(group_id, app=celery_app)
    if group_result is None:
        if child_ids:
            group_result = GroupResult(
                group_id,
                [AsyncResult(child_id, app=celery_app) for child_id in child_ids],
                app=celery_app,
            )
        else:
            logger.warning("Best-effort chord missing group result: %s", group_id)
            return {"status": "failed", "reason": "group result not found", "group_id": group_id}

    if not group_result.ready():
        if started_at is None:
            started_at = time.time()
        elapsed = time.time() - started_at
        if elapsed >= max_wait_seconds:
            logger.warning("Best-effort chord timed out after %s seconds", int(elapsed))
            return {"status": "failed", "reason": "timeout", "group_id": group_id}
        max_retries = _compute_max_retries(max_wait_seconds, poll_interval)
        raise self.retry(
            countdown=poll_interval,
            max_retries=max_retries,
            kwargs={
                "payload": {
                    **payload,
                    "group_id": group_id,
                    "child_ids": child_ids,
                    "started_at": started_at,
                }
            },
        )

    results, errors = _collect_best_effort_results(group_result, task_metadata)
    success_ratio = _compute_success_ratio(len(results), len(results) + len(errors))
    if errors:
        CHORD_PARTIAL_FAILURES.inc()
    if success_ratio < min_success_ratio:
        if on_error is not None:
            error_callback = _coerce_signature(on_error)
            error_callback.apply_async(args=[results, errors])
        logger.warning(
            "Best-effort chord failed with success_ratio %s (min %s)",
            success_ratio,
            min_success_ratio,
        )
        raise ValueError("Best-effort chord success ratio below threshold")

    callback = _coerce_signature(body)
    callback_result = callback.apply_async(args=[results, errors])
    return {
        "status": "triggered",
        "group_id": group_id,
        "callback_task_id": callback_result.id,
        "success_ratio": success_ratio,
        "error_count": len(errors),
    }


def _coerce_signature(value: Any) -> Any:
    return signature(value, app=celery_app)


def _collect_best_effort_results(
    group_result: GroupResult,
    task_metadata: list[dict[str, Any]] | None,
) -> tuple[list[Any], list[dict[str, Any]]]:
    results: list[Any] = []
    errors: list[dict[str, Any]] = []
    children = group_result.results or []
    for index, child in enumerate(children):
        with allow_join_result():
            value = child.get(propagate=False)
        metadata = {}
        if task_metadata and index < len(task_metadata):
            metadata = task_metadata[index]
        task_name = metadata.get("task_name")
        res_id = metadata.get("res_id")
        if isinstance(value, BaseException):
            error_type = type(value).__name__
            errors.append(
                {
                    "task_name": task_name,
                    "res_id": res_id,
                    "error": str(value),
                    "error_type": error_type,
                }
            )
            logger.warning(
                "Best-effort chord task failed: task=%s res_id=%s error_type=%s error=%s",
                task_name,
                res_id,
                error_type,
                value,
            )
        else:
            results.append(value)
    return results, errors


def _compute_success_ratio(success_count: int, total_count: int) -> float:
    if total_count <= 0:
        return 0.0
    return success_count / total_count


def _compute_max_retries(max_wait_seconds: int, poll_interval: int) -> int:
    if poll_interval <= 0:
        return 1
    return max(1, ceil(max_wait_seconds / poll_interval))


def _load_fanout_res_ids(fanout_source: str) -> list[int]:
    if not fanout_source.startswith("redis:"):
        raise ValueError(f"Unsupported fanout source: {fanout_source}")
    key = fanout_source.replace("redis:", "", 1)
    if not key:
        raise ValueError("Fanout source key is required")
    cache = ScraperResIdCache(key=key)
    return cache.get_res_ids()
